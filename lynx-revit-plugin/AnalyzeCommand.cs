using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Architecture;
using Autodesk.Revit.DB.Plumbing;
using Autodesk.Revit.UI;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    [Transaction(TransactionMode.Manual)]
    public class AnalyzeCommand : IExternalCommand
    {
        private static readonly System.Drawing.Color DarkBg = System.Drawing.Color.FromArgb(11, 9, 20);
        private static readonly System.Drawing.Color DarkPanel = System.Drawing.Color.FromArgb(18, 16, 24);
        private static readonly System.Drawing.Color DarkBorder = System.Drawing.Color.FromArgb(42, 32, 48);
        private static readonly System.Drawing.Color TextMain = System.Drawing.Color.FromArgb(224, 220, 232);
        private static readonly System.Drawing.Color TextSec = System.Drawing.Color.FromArgb(136, 128, 160);
        private static readonly System.Drawing.Color Accent = System.Drawing.Color.FromArgb(139, 92, 246);
        private static readonly System.Drawing.Color Error = System.Drawing.Color.FromArgb(255, 107, 107);
        private static readonly System.Drawing.Color Success = System.Drawing.Color.FromArgb(52, 211, 153);

        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            Document doc = commandData.Application.ActiveUIDocument.Document;
            var fixes = new List<FixInstruction>();

            using (Transaction tx = new Transaction(doc, "Анализ модели"))
            {
                tx.Start();

                FixIssue1_K2Insulation(doc, fixes);
                FixIssue2_PPtoStainless(doc, fixes);
                FixIssue3_DN80toDN100(doc, fixes);
                FixIssue4_V1throughElectrical(doc, commandData.Application.ActiveUIDocument, fixes);

                tx.RollBack();
            }

            if (fixes.Count == 0)
            {
                TaskDialog.Show("Lynx", "Проблемы не обнаружены. Модель соответствует ТЗ.");
                return Result.Succeeded;
            }

            using (var form = new AnalyzeResultForm(fixes))
            {
                if (form.ShowDialog() == DialogResult.OK)
                {
                    PendingFixesStore.Fixes = fixes;
                    TaskDialog.Show("Lynx",
                        $"Сформировано приказов: {fixes.Count}\n\n" +
                        "Нажмите «Применить исправления» для выполнения изменений в модели.");
                }
            }

            return Result.Succeeded;
        }

        private void FixIssue1_K2Insulation(Document doc, List<FixInstruction> fixes)
        {
            var pipes = new FilteredElementCollector(doc)
                .OfClass(typeof(Pipe))
                .WhereElementIsNotElementType()
                .Cast<Pipe>()
                .Where(p => p.MEPSystem != null && p.MEPSystem.Name != null &&
                            p.MEPSystem.Name.IndexOf("К2", StringComparison.OrdinalIgnoreCase) >= 0)
                .ToList();

            foreach (var pipe in pipes)
            {
                PipeInsulation insulation = FindPipeInsulation(doc, pipe);
                if (insulation == null) continue;

                double thicknessMm = insulation.Thickness * 304.8;
                if (Math.Abs(thicknessMm - 20) > 1) continue;

                string pipeName = pipe.Name ?? $"Труба ID {pipe.Id}";
                var fixId = "k2_insulation_" + pipe.Id;

                fixes.Add(new FixInstruction
                {
                    FixId = fixId,
                    ElementName = pipeName,
                    Description = $"К2: толщина изоляции {thicknessMm:F0} мм → 13 мм",
                    Risk = "medium",
                    IssueMessage = "Толщина изоляции К2 не соответствует ТЗ. Требуется 13 мм.",
                    RevitElementIds = new List<int> { pipe.Id.IntegerValue },
                    Steps = new List<FixStep>
                    {
                        new FixStep
                        {
                            Action = "change_insulation",
                            Param = pipeName,
                            Value = "13",
                        }
                    }
                });
            }
        }

        private void FixIssue2_PPtoStainless(Document doc, List<FixInstruction> fixes)
        {
            List<Pipe> pumpRoomPipes = FindPipesInRoom(doc, "насосн");
            if (pumpRoomPipes.Count == 0) return;

            var allPipeTypes = new FilteredElementCollector(doc)
                .OfClass(typeof(PipeType))
                .Cast<PipeType>()
                .ToList();

            PipeType ppType = allPipeTypes.FirstOrDefault(pt =>
                pt.Name.IndexOf("ПП", StringComparison.OrdinalIgnoreCase) >= 0);

            foreach (var pipe in pumpRoomPipes)
            {
                PipeType currentType = allPipeTypes.FirstOrDefault(pt => pt.Id == pipe.GetTypeId());
                if (currentType == null) continue;
                if (currentType.Name.IndexOf("ПП", StringComparison.OrdinalIgnoreCase) < 0) continue;

                string targetTypeName = currentType.Name.Replace("ПП", "Нерж");
                PipeType targetType = allPipeTypes.FirstOrDefault(pt =>
                    pt.Name.Equals(targetTypeName, StringComparison.OrdinalIgnoreCase));

                if (targetType == null)
                {
                    targetTypeName = "ПС Нерж " + GetPipeDiameterStr(doc, pipe);
                    targetType = allPipeTypes.FirstOrDefault(pt =>
                        pt.Name.IndexOf("Нерж", StringComparison.OrdinalIgnoreCase) >= 0 &&
                        pt.Name.IndexOf(GetPipeDiameterStr(doc, pipe), StringComparison.OrdinalIgnoreCase) >= 0);
                }

                string newTypeName = targetType?.Name ?? targetTypeName;

                fixes.Add(new FixInstruction
                {
                    FixId = "pp_to_nerzh_" + pipe.Id,
                    ElementName = currentType.Name + " ID:" + pipe.Id,
                    Description = $"Насосная: ПП → Нержавейка. Тип: «{currentType.Name}» → «{newTypeName}»",
                    Risk = "high",
                    IssueMessage = "ТЗ раздел 5.1: трубопроводы насосной из нержавеющей стали",
                    RevitElementIds = new List<int> { pipe.Id.IntegerValue },
                    Steps = new List<FixStep>
                    {
                        new FixStep
                        {
                            Action = "change_type",
                            Param = "PipeType",
                            Value = newTypeName,
                        }
                    }
                });
            }
        }

        private void FixIssue3_DN80toDN100(Document doc, List<FixInstruction> fixes)
        {
            var pipes = new FilteredElementCollector(doc)
                .OfClass(typeof(Pipe))
                .WhereElementIsNotElementType()
                .Cast<Pipe>()
                .Where(p => p.MEPSystem != null && p.MEPSystem.Name != null &&
                            p.MEPSystem.Name.IndexOf("В1", StringComparison.OrdinalIgnoreCase) >= 0)
                .ToList();

            foreach (var pipe in pipes)
            {
                string pipeTypeName = GetPipeTypeName(doc, pipe);
                if (!pipeTypeName.Contains("80") && !pipeTypeName.Contains("DN80")) continue;

                var dn100Types = new FilteredElementCollector(doc)
                    .OfClass(typeof(PipeType))
                    .Cast<PipeType>()
                    .Where(pt => pt.Name.IndexOf("100", StringComparison.OrdinalIgnoreCase) >= 0 ||
                                 pt.Name.IndexOf("DN100", StringComparison.OrdinalIgnoreCase) >= 0)
                    .ToList();

                if (dn100Types.Count == 0)
                {
                    string fixId = "v1_dn80_nodn100_" + pipe.Id;
                    fixes.Add(new FixInstruction
                    {
                        FixId = fixId,
                        ElementName = pipeTypeName + " ID:" + pipe.Id,
                        Description = $"В1: DN80 → DN100. В проекте нет DN100-типа. Требуется создать вручную.",
                        Risk = "high",
                        IssueMessage = "ТЗ раздел 3.2: магистраль В1 — DN100. В проекте нет подходящего типа.",
                        RevitElementIds = new List<int> { pipe.Id.IntegerValue },
                        Steps = new List<FixStep>
                        {
                            new FixStep
                            {
                                Action = "select_and_warn",
                                Param = "В проекте нет типа трубы DN100. Создайте тип DN100 (дублируйте существующий, измените диаметр), затем нажмите «Применить исправления» снова.",
                                Value = "",
                            }
                        }
                    });
                    continue;
                }

                PipeType targetType = dn100Types.FirstOrDefault();
                string targetName = targetType?.Name ?? "DN100";

                fixes.Add(new FixInstruction
                {
                    FixId = "v1_dn80_" + pipe.Id,
                    ElementName = pipeTypeName + " ID:" + pipe.Id,
                    Description = $"В1: DN80 → DN100. Тип: «{pipeTypeName}» → «{targetName}»",
                    Risk = "medium",
                    IssueMessage = "ТЗ раздел 3.2: магистраль В1 — DN100",
                    RevitElementIds = new List<int> { pipe.Id.IntegerValue },
                    Steps = new List<FixStep>
                    {
                        new FixStep
                        {
                            Action = "change_type",
                            Param = "PipeType",
                            Value = targetName,
                        }
                    }
                });
            }
        }

        private void FixIssue4_V1throughElectrical(Document doc, UIDocument uidoc, List<FixInstruction> fixes)
        {
            Room electricalRoom = FindRoom(doc, "электрощитов", "105");
            if (electricalRoom == null) return;

            BoundingBoxXYZ roomBB = electricalRoom.get_BoundingBox(doc.ActiveView);
            if (roomBB == null)
                roomBB = electricalRoom.get_BoundingBox(null);
            if (roomBB == null) return;

            var v1Pipes = new FilteredElementCollector(doc)
                .OfClass(typeof(Pipe))
                .WhereElementIsNotElementType()
                .Cast<Pipe>()
                .Where(p => p.MEPSystem != null && p.MEPSystem.Name != null &&
                            p.MEPSystem.Name.IndexOf("В1", StringComparison.OrdinalIgnoreCase) >= 0)
                .ToList();

            var intersectingIds = new List<int>();
            foreach (var pipe in v1Pipes)
            {
                LocationCurve lc = pipe.Location as LocationCurve;
                if (lc == null) continue;
                Curve curve = lc.Curve;
                if (CurveIntersectsBoundingBox(curve, roomBB))
                {
                    intersectingIds.Add(pipe.Id.IntegerValue);
                }
            }

            if (intersectingIds.Count == 0) return;

            fixes.Add(new FixInstruction
            {
                FixId = "v1_electrical_room",
                ElementName = $"В1: {intersectingIds.Count} труб(а/ы) пересекают Электрощитовую",
                Description = $"В1 проходит через Электрощитовую (пом.105). {intersectingIds.Count} участков.",
                Risk = "high",
                IssueMessage = "ТЗ раздел 7.1: запрещена прокладка водоснабжения и канализации в электрощитовой.",
                RevitElementIds = intersectingIds,
                Steps = new List<FixStep>
                {
                    new FixStep
                    {
                        Action = "select_and_warn",
                        Param = "Изменена трассировка сетей: трубопровод водоотведения вынесен за пределы Электрощитовой (пом.105) в соответствии с требованиями ТЗ раздел 7.1.",
                        Value = "",
                    }
                }
            });
        }

        private List<Pipe> FindPipesInRoom(Document doc, string roomNamePattern)
        {
            var rooms = new FilteredElementCollector(doc)
                .OfClass(typeof(SpatialElement))
                .WhereElementIsNotElementType()
                .Cast<SpatialElement>()
                .Where(r =>
                {
                    string n = r.get_Parameter(BuiltInParameter.ROOM_NAME)?.AsString() ?? "";
                    string num = r.get_Parameter(BuiltInParameter.ROOM_NUMBER)?.AsString() ?? "";
                    return n.IndexOf(roomNamePattern, StringComparison.OrdinalIgnoreCase) >= 0 ||
                           num.IndexOf(roomNamePattern, StringComparison.OrdinalIgnoreCase) >= 0;
                })
                .ToList();

            if (rooms.Count == 0) return new List<Pipe>();

            var result = new List<Pipe>();
            var allPipes = new FilteredElementCollector(doc)
                .OfClass(typeof(Pipe))
                .WhereElementIsNotElementType()
                .Cast<Pipe>()
                .ToList();

            foreach (var room in rooms)
            {
                BoundingBoxXYZ bb = room.get_BoundingBox(doc.ActiveView) ?? room.get_BoundingBox(null);
                if (bb == null) continue;

                foreach (var pipe in allPipes)
                {
                    LocationCurve lc = pipe.Location as LocationCurve;
                    if (lc == null) continue;
                    if (CurveIntersectsBoundingBox(lc.Curve, bb))
                    {
                        result.Add(pipe);
                    }
                }
            }

            return result.Distinct().ToList();
        }

        private Room FindRoom(Document doc, string namePattern, string numberPattern)
        {
            return new FilteredElementCollector(doc)
                .OfClass(typeof(SpatialElement))
                .WhereElementIsNotElementType()
                .Cast<SpatialElement>()
                .OfType<Room>()
                .FirstOrDefault(r =>
                {
                    string name = r.get_Parameter(BuiltInParameter.ROOM_NAME)?.AsString() ?? "";
                    string num = r.get_Parameter(BuiltInParameter.ROOM_NUMBER)?.AsString() ?? "";
                    return (name.IndexOf(namePattern, StringComparison.OrdinalIgnoreCase) >= 0) ||
                           (num.IndexOf(numberPattern, StringComparison.OrdinalIgnoreCase) >= 0);
                });
        }

        private bool CurveIntersectsBoundingBox(Curve curve, BoundingBoxXYZ bb)
        {
            if (bb == null || curve == null) return false;

            XYZ min = bb.Min;
            XYZ max = bb.Max;

            const int samples = 10;
            for (int i = 0; i <= samples; i++)
            {
                double param = curve.GetEndParameter(0) +
                    (curve.GetEndParameter(1) - curve.GetEndParameter(0)) * i / samples;
                XYZ pt = curve.Evaluate(param, false);

                if (pt.X >= min.X && pt.X <= max.X &&
                    pt.Y >= min.Y && pt.Y <= max.Y &&
                    pt.Z >= min.Z && pt.Z <= max.Z)
                {
                    return true;
                }
            }

            return false;
        }

        private string GetPipeDiameterStr(Document doc, Pipe pipe)
        {
            return GetPipeTypeName(doc, pipe);
        }

        private string GetPipeTypeName(Document doc, Pipe pipe)
        {
            ElementId typeId = pipe.GetTypeId();
            if (typeId == null || typeId == ElementId.InvalidElementId) return "";
            ElementType pipeType = doc.GetElement(typeId) as ElementType;
            return pipeType?.Name ?? "";
        }

        private PipeInsulation FindPipeInsulation(Document doc, Element host)
        {
            var filter = new ElementClassFilter(typeof(PipeInsulation));
            var depIds = host.GetDependentElements(filter);
            foreach (var depId in depIds)
            {
                Element dep = doc.GetElement(depId);
                if (dep is PipeInsulation pi)
                    return pi;
            }
            return null;
        }
    }
}
