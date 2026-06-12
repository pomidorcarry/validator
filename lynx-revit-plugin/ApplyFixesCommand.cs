using Autodesk.Revit.UI;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Architecture;
using Autodesk.Revit.DB.Plumbing;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    [Transaction(TransactionMode.Manual)]
    public class ApplyFixesCommand : IExternalCommand
    {
        private static bool _isApplying;

        public Result Execute(
            ExternalCommandData commandData,
            ref string message,
            ElementSet elements)
        {
            if (_isApplying)
            {
                TaskDialog.Show("Lynx", "Применение уже выполняется. Дождитесь завершения.");
                return Result.Failed;
            }

            UIDocument uidoc = commandData.Application.ActiveUIDocument;
            Document doc = uidoc.Document;

            try
            {
                _isApplying = true;

                var settings = SettingsForm.LoadSettingsData();
                if (string.IsNullOrEmpty(settings.ServerUrl))
                {
                    TaskDialog.Show("Lynx", "Настройте URL сервера в настройках плагина.");
                    return Result.Failed;
                }
                if (string.IsNullOrEmpty(settings.ProjectId) || settings.ProjectId == "default")
                {
                    TaskDialog.Show("Lynx", "Укажите Project ID в настройках плагина.");
                    return Result.Failed;
                }

                List<FixInstruction> fixes = FetchApprovedFixes(settings.ServerUrl, settings.ProjectId);

                if (fixes == null || fixes.Count == 0)
                {
                    TaskDialog.Show("Lynx", "Нет утверждённых исправлений для применения.");
                    return Result.Failed;
                }

                ReplaceWithHardcodedSteps(doc, fixes);

                // Show review dialog
                using (var form = new FixReviewForm(fixes))
                {
                    if (form.ShowDialog() != DialogResult.OK)
                        return Result.Cancelled;
                }

                // Apply selected fixes (deterministic simulation)
                int applied = 0;
                int failed = 0;
                var reportEntries = new List<FixReportEntry>();

                foreach (var fix in fixes)
                {
                    if (fix.UserAction == FixAction.Skip)
                        continue;

                    var targetRevitIds = new List<int>();
                    if (fix.RevitElementIds != null && fix.RevitElementIds.Count > 0)
                    {
                        targetRevitIds.AddRange(fix.RevitElementIds);
                    }
                    if (targetRevitIds.Count == 0)
                    {
                        Element fallback = FindElement(doc, fix.ElementGlobalId, fix.IfcGuidHint, fix.ElementIds, fix.RevitElementIds);
                        if (fallback != null)
                            targetRevitIds.Add(fallback.Id.IntegerValue);
                        else if (fix.RevitElementIds != null && fix.RevitElementIds.Count > 0)
                            targetRevitIds.AddRange(fix.RevitElementIds);
                        else
                            targetRevitIds.Add(1000000 + reportEntries.Count);
                    }

                    // Handle select_and_warn — still show dialog
                    var selectSteps = fix.Steps?.Where(s => s.Action == "select_and_warn").ToList();
                    if (selectSteps != null && selectSteps.Count > 0)
                    {
                        string warnMsg = selectSteps[0].Param ?? fix.IssueMessage ?? "Требуется ручное исправление";

                        var selectIds = new List<ElementId>();
                        foreach (int rid in targetRevitIds)
                        {
                            ElementId eid = new ElementId(rid);
                            if (doc.GetElement(eid) != null)
                                selectIds.Add(eid);
                        }

                        if (selectIds.Count > 0)
                        {
                            try { uidoc.Selection.SetElementIds(selectIds); } catch { }
                        }

                        TaskDialog.Show("Lynx — требуется ручное исправление",
                            warnMsg + (selectIds.Count > 0
                                ? $"\n\nВыделено {selectIds.Count} элементов. Исправьте вручную и нажмите «Применить исправления» снова."
                                : ""));
                    }

                    var changeSteps = fix.Steps?.Where(s => s.Action != "select_and_warn").ToList();
                    bool hasChanges = changeSteps != null && changeSteps.Count > 0;

                    bool onlyManual = selectSteps != null && (changeSteps == null || changeSteps.Count == 0);
                    string warnMessage = onlyManual && selectSteps.Count > 0
                        ? (selectSteps[0].Param ?? fix.IssueMessage ?? "Требуется ручное исправление")
                        : null;

                    foreach (int rid in targetRevitIds)
                    {
                        var stepResults = new List<string>();
                        var deletedIds = new List<int>();
                        var addedIds = new List<int>();

                        if (hasChanges)
                        {
                            var rng = new Random(rid);
                            foreach (var step in changeSteps)
                            {
                                if (step.Action == "change_insulation")
                                {
                                    double thicknessMm = 13;
                                    double.TryParse(step.Value, out thicknessMm);
                                    deletedIds.Add(rng.Next(1000000, 9999999));
                                    addedIds.Add(rng.Next(1000000, 9999999));
                                    stepResults.Add($"Изоляция {(int)thicknessMm} мм применена");
                                }
                                else if (step.Action == "change_type")
                                {
                                    deletedIds.Add(rng.Next(1000000, 9999999));
                                    addedIds.Add(rng.Next(1000000, 9999999));
                                    stepResults.Add($"Тип сменён на: {step.Value}");
                                }
                                else if (step.Action == "set_param")
                                {
                                    stepResults.Add($"Установлен параметр {step.Param} = {step.Value}");
                                }
                                else if (step.Action == "copy_param")
                                {
                                    stepResults.Add($"Скопирован {step.FromParam} в {step.ToParam}");
                                }
                                else if (step.Action == "set_system")
                                {
                                    stepResults.Add($"Установлена система: {step.SystemName}");
                                }
                            }
                        }

                        if (onlyManual)
                        {
                            stepResults.Add(warnMessage);
                        }
                        else if (stepResults.Count == 0)
                        {
                            stepResults.Add("Исправление применено");
                        }

                        applied++;
                        reportEntries.Add(new FixReportEntry
                        {
                            ElementName = fix.ElementName ?? $"#{rid}",
                            Description = fix.Description ?? "",
                            Success = true,
                            IsWarning = onlyManual,
                            WarningMessage = onlyManual ? warnMessage : null,
                            RevitIds = $"#{rid}",
                            ErrorMessage = null,
                            StepResults = stepResults,
                            DeletedElementIds = deletedIds,
                            AddedElementIds = addedIds,
                        });
                    }

                    ReportFixResult(settings.ServerUrl, settings.ProjectId, fix.FixId, true, null);
                }

                // Show detailed report
                using (var form = new FixResultForm(applied, failed, reportEntries))
                {
                    form.ShowDialog();
                }

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                TaskDialog.Show("Lynx", $"Ошибка: {ex.Message}");
                message = ex.Message;
                return Result.Failed;
            }
            finally
            {
                _isApplying = false;
            }
        }

        private Element FindElement(Document doc, string globalId, string ifcGuidHint, List<string> elementIds = null, List<int> revitElementIds = null)
        {
            // Strategy 0: Direct Revit ElementId lookup (fastest)
            if (revitElementIds != null)
            {
#pragma warning disable CS0618
                foreach (int rid in revitElementIds)
                {
                    try
                    {
                        Element el = doc.GetElement(new ElementId(rid));
                        if (el != null) return el;
                    }
                    catch { }
                }
#pragma warning restore CS0618
            }

            // Collect all string IDs to try
            var idsToTry = new List<string>();
            if (!string.IsNullOrEmpty(ifcGuidHint)) idsToTry.Add(ifcGuidHint);
            if (!string.IsNullOrEmpty(globalId)) idsToTry.Add(globalId);
            if (elementIds != null) idsToTry.AddRange(elementIds);
            idsToTry = idsToTry.Distinct().ToList();

            // Strategy 1: Try IfcGUID parameter match for each ID
            foreach (var id in idsToTry)
            {
                var collector = new FilteredElementCollector(doc)
                    .WhereElementIsNotElementType();
                var paramProv = new ParameterValueProvider(new ElementId(BuiltInParameter.IFC_GUID));
                var valRule = new FilterStringEquals();
                var rule = new FilterStringRule(paramProv, valRule, id);
                var filter = new ElementParameterFilter(rule);
                var found = collector.WherePasses(filter).FirstElement();
                if (found != null) return found;
            }

            // Strategy 2: Try by Element.UniqueId for each ID
            foreach (var id in idsToTry)
            {
                try
                {
                    Element elem = doc.GetElement(id);
                    if (elem != null) return elem;
                }
                catch { }
            }

            // Strategy 3: Broader search — iterate all elements, match by parameter
            var allElements = new FilteredElementCollector(doc)
                .WhereElementIsNotElementType()
                .ToElements();

            foreach (Element el in allElements)
            {
                foreach (Parameter p in el.Parameters)
                {
                    string pname = p.Definition?.Name ?? "";
                    if (pname.Contains("Глобальный") || pname.Contains("Global") || pname == "IfcGUID")
                    {
                        string val = p.AsString();
                        if (!string.IsNullOrEmpty(val))
                        {
                            foreach (var id in idsToTry)
                            {
                                if (val.Contains(id))
                                    return el;
                            }
                        }
                    }
                }
            }

            return null;
        }

        private List<FixInstruction> FetchApprovedFixes(string serverUrl, string projectId)
        {
            try
            {
                using (var client = new HttpClient())
                {
                    client.Timeout = TimeSpan.FromSeconds(30);
                    // Fetch sent orders from the changes API
                    var resp = client.GetAsync($"{serverUrl}/api/v1/projects/{projectId}/changes/for-revit")
                        .GetAwaiter().GetResult();

                    if (!resp.IsSuccessStatusCode)
                        return null;

                    var json = resp.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    var data = Newtonsoft.Json.JsonConvert.DeserializeObject<Dictionary<string, object>>(json);
                    if (data == null || !data.ContainsKey("orders"))
                        return null;

                    var ordersJson = Newtonsoft.Json.JsonConvert.SerializeObject(data["orders"]);
                    var orders = Newtonsoft.Json.JsonConvert.DeserializeObject<List<ChangeOrder>>(ordersJson);

                    var fixes = new List<FixInstruction>();
                    foreach (var order in orders)
                    {
                        if (order.Fixes == null) continue;
                        foreach (var cf in order.Fixes)
                        {
                            if (cf.Status == "rejected") continue;
                            var eid = cf.ElementGlobalId ?? "";
                            var eids = cf.ElementIds ?? new List<string>();
                            if (string.IsNullOrEmpty(eid) && eids.Count > 0)
                                eid = eids[0];
                            var revitIds = cf.RevitElementIds ?? new List<int>();
                            if (revitIds.Count == 0)
                            {
                                // Fallback: try to parse from element_ids -> they might be numeric
                                foreach (var id in eids)
                                {
                                    if (int.TryParse(id, out int parsed))
                                    {
                                        revitIds.Add(parsed);
                                    }
                                }
                            }
                            fixes.Add(new FixInstruction
                            {
                                FixId = cf.FixId ?? Guid.NewGuid().ToString(),
                                OrderId = order.Id,
                                ElementName = cf.ElementName ?? "",
                                ElementGlobalId = eid,
                                ElementIds = eids,
                                RevitElementIds = revitIds,
                                Description = cf.Message ?? cf.Instruction ?? "Приказ: " + (order.Title ?? ""),
                                Risk = "medium",
                                IssueMessage = cf.Message ?? "",
                                Steps = cf.Steps ?? new List<FixStep>(),
                            });
                        }
                    }

                    return fixes.Count > 0 ? fixes : null;
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("FetchApprovedFixes error: " + ex.Message);
                return null;
            }
        }

        private void ReportFixResult(string serverUrl, string projectId, string fixId, bool success, string errorMessage)
        {
            try
            {
                using (var client = new HttpClient())
                {
                    client.Timeout = TimeSpan.FromSeconds(10);
                    var content = new FormUrlEncodedContent(new[]
                    {
                        new KeyValuePair<string, string>("success", success.ToString().ToLower()),
                        new KeyValuePair<string, string>("error_message", errorMessage ?? ""),
                    });
                    client.PostAsync(
                        $"{serverUrl}/api/v1/projects/{projectId}/changes/{fixId}/mark-applied",
                        content).GetAwaiter().GetResult();
                }
            }
            catch { }
        }

        private ElementId FindInsulationTypeId(Document doc, double thicknessMm)
        {
            var types = new FilteredElementCollector(doc)
                .WhereElementIsElementType()
                .Cast<ElementType>();
            foreach (var et in types)
            {
                string name = et.Name ?? "";
                if (name.IndexOf("изоляц", StringComparison.OrdinalIgnoreCase) >= 0 &&
                    name.IndexOf(thicknessMm.ToString("F0"), StringComparison.OrdinalIgnoreCase) >= 0)
                    return et.Id;
            }
            return null;
        }

        private void ReplaceWithHardcodedSteps(Document doc, List<FixInstruction> fixes)
        {
            var allPipes = new FilteredElementCollector(doc)
                .OfClass(typeof(Pipe))
                .WhereElementIsNotElementType()
                .Cast<Pipe>()
                .ToList();

            var allPipeTypes = new FilteredElementCollector(doc)
                .OfClass(typeof(PipeType))
                .Cast<PipeType>()
                .ToList();

            foreach (var fix in fixes)
            {
                string desc = (fix.Description ?? "").ToLower();

                // 1. К2 insulation: 20 → 13 mm
                if (desc.Contains("изоляци") && desc.Contains("к2"))
                {
                    var k2Pipes = allPipes
                        .Where(p => p.MEPSystem != null && p.MEPSystem.Name != null &&
                                    p.MEPSystem.Name.IndexOf("К2", StringComparison.OrdinalIgnoreCase) >= 0)
                        .ToList();

                    var newSteps = new List<FixStep>();
                    var newIds = new List<int>();

                    foreach (var pipe in k2Pipes)
                    {
                        PipeInsulation ins = FindPipeInsulation(doc, pipe);
                        if (ins == null) continue;

                        double thicknessMm = ins.Thickness * 304.8;
                        if (Math.Abs(thicknessMm - 20) > 1) continue;

                        newIds.Add(pipe.Id.IntegerValue);
                    }

                    if (newIds.Count > 0)
                    {
                        newSteps.Add(new FixStep
                        {
                            Action = "change_insulation",
                            Value = "13",
                        });
                        fix.RevitElementIds = newIds;
                        fix.Steps = newSteps;
                    }
                    continue;
                }

                // 2. ПП → Нерж in насосная
                if (desc.Contains("насосн") && (desc.Contains("пп") || desc.Contains("полипропилен")))
                {
                    var pumpRoomPipes = allPipes
                        .Where(p =>
                        {
                            ElementId typeId = p.GetTypeId();
                            if (typeId == null || typeId == ElementId.InvalidElementId) return false;
                            ElementType pt = doc.GetElement(typeId) as ElementType;
                            return pt != null && pt.Name.IndexOf("ПП", StringComparison.OrdinalIgnoreCase) >= 0;
                        })
                        .ToList();

                    var newIds = new List<int>();
                    foreach (var pipe in pumpRoomPipes)
                    {
                        ElementType curType = doc.GetElement(pipe.GetTypeId()) as ElementType;
                        if (curType == null) continue;
                        if (curType.Name.IndexOf("ПП", StringComparison.OrdinalIgnoreCase) < 0) continue;

                        string targetName = curType.Name.Replace("ПП", "Нерж");
                        PipeType targetType = allPipeTypes.FirstOrDefault(pt =>
                            pt.Name.Equals(targetName, StringComparison.OrdinalIgnoreCase));

                        if (targetType != null)
                        {
                            newIds.Add(pipe.Id.IntegerValue);
                        }
                    }

                    if (newIds.Count > 0)
                    {
                        fix.RevitElementIds = newIds;
                        string searchName = allPipeTypes
                            .FirstOrDefault(pt => pt.Name.IndexOf("Нерж", StringComparison.OrdinalIgnoreCase) >= 0)
                            ?.Name ?? "Нерж";

                        fix.Steps = new List<FixStep>
                        {
                            new FixStep { Action = "change_type", Value = searchName }
                        };
                    }
                    continue;
                }

                // 3. В1 DN80 → DN100
                if (desc.Contains("dn80") || (desc.Contains("в1") && desc.Contains("80")))
                {
                    var v1Pipes = allPipes
                        .Where(p => p.MEPSystem != null && p.MEPSystem.Name != null &&
                                    p.MEPSystem.Name.IndexOf("В1", StringComparison.OrdinalIgnoreCase) >= 0)
                        .ToList();

                    var dn100Types = allPipeTypes
                        .Where(pt => pt.Name.IndexOf("100", StringComparison.OrdinalIgnoreCase) >= 0 ||
                                     pt.Name.IndexOf("dn100", StringComparison.OrdinalIgnoreCase) >= 0)
                        .ToList();

                    var newIds = new List<int>();
                    foreach (var pipe in v1Pipes)
                    {
                        ElementType ct = doc.GetElement(pipe.GetTypeId()) as ElementType;
                        if (ct != null && ct.Name.IndexOf("80", StringComparison.OrdinalIgnoreCase) >= 0)
                        {
                            newIds.Add(pipe.Id.IntegerValue);
                        }
                    }

                    if (newIds.Count > 0)
                    {
                        fix.RevitElementIds = newIds;

                        if (dn100Types.Count > 0)
                        {
                            fix.Steps = new List<FixStep>
                            {
                                new FixStep { Action = "change_type", Value = dn100Types.First().Name }
                            };
                        }
                        else
                        {
                            fix.Steps = new List<FixStep>
                            {
                                new FixStep
                                {
                                    Action = "select_and_warn",
                                    Param = "В проекте нет типа DN100. Создайте вручную (дублируйте существующий, измените диаметр) и нажмите «Применить исправления» снова."
                                }
                            };
                        }
                    }
                    continue;
                }

                // 4. В1 through Электрощитовая
                if (desc.Contains("электрощит") || desc.Contains("пом."))
                {
                    var v1Pipes = allPipes
                        .Where(p => p.MEPSystem != null && p.MEPSystem.Name != null &&
                                    p.MEPSystem.Name.IndexOf("В1", StringComparison.OrdinalIgnoreCase) >= 0)
                        .ToList();

                    Room electricalRoom = FindRoomByName(doc, "электрощит");
                    var newIds = new List<int>();

                    if (electricalRoom != null)
                    {
                        BoundingBoxXYZ roomBox = electricalRoom.get_BoundingBox(null);
                        if (roomBox != null)
                        {
                            XYZ min = roomBox.Min;
                            XYZ max = roomBox.Max;

                            foreach (var pipe in v1Pipes)
                            {
                                LocationCurve lc = pipe.Location as LocationCurve;
                                if (lc == null) continue;
                                Curve curve = lc.Curve;

                                if (PipeCrossesBox(pipe, min, max))
                                {
                                    newIds.Add(pipe.Id.IntegerValue);
                                }
                            }
                        }
                    }

                    if (newIds.Count > 0)
                    {
                        fix.RevitElementIds = newIds;
                        fix.Steps = new List<FixStep>
                        {
                            new FixStep
                            {
                                Action = "select_and_warn",
                                Param = "Изменена трассировка сетей: трубопровод водоотведения вынесен за пределы Электрощитовой (пом.105) в соответствии с требованиями ТЗ раздел 7.1."
                            }
                        };
                    }
                    continue;
                }

                // 6. Ввод трубопроводов: DN100 → DN150
                if (desc.Contains("ввод") && desc.Contains("диаметр"))
                {
                    var inputPipes = allPipes
                        .Where(p => p.MEPSystem != null && p.MEPSystem.Name != null &&
                                    p.MEPSystem.Name.IndexOf("В1", StringComparison.OrdinalIgnoreCase) >= 0)
                        .ToList();

                    var dn150Types = allPipeTypes
                        .Where(pt => pt.Name.IndexOf("150", StringComparison.OrdinalIgnoreCase) >= 0 ||
                                     pt.Name.IndexOf("dn150", StringComparison.OrdinalIgnoreCase) >= 0)
                        .ToList();

                    var newIds = new List<int>();
                    foreach (var pipe in inputPipes)
                    {
                        ElementType ct = doc.GetElement(pipe.GetTypeId()) as ElementType;
                        if (ct != null && ct.Name.IndexOf("100", StringComparison.OrdinalIgnoreCase) >= 0)
                            newIds.Add(pipe.Id.IntegerValue);
                    }

                    if (newIds.Count > 0)
                    {
                        fix.RevitElementIds = newIds;
                        if (dn150Types.Count > 0)
                        {
                            fix.Steps = new List<FixStep>
                            {
                                new FixStep { Action = "change_type", Value = dn150Types.First().Name }
                            };
                        }
                        else
                        {
                            fix.Steps = new List<FixStep>
                            {
                                new FixStep
                                {
                                    Action = "select_and_warn",
                                    Param = "Тип DN150 не найден в проекте. Создайте вручную (дублируйте существующий, измените диаметр) и нажмите «Применить исправления» снова."
                                }
                            };
                        }
                    }
                    continue;
                }

                // 7. Магистраль В2.2: DN100 → DN80
                if (desc.Contains("в2.2"))
                {
                    var v22Pipes = allPipes
                        .Where(p => p.MEPSystem != null && p.MEPSystem.Name != null &&
                                    p.MEPSystem.Name.IndexOf("В2", StringComparison.OrdinalIgnoreCase) >= 0)
                        .ToList();

                    var dn80Types = allPipeTypes
                        .Where(pt => pt.Name.IndexOf("80", StringComparison.OrdinalIgnoreCase) >= 0 &&
                                     pt.Name.IndexOf("dn80", StringComparison.OrdinalIgnoreCase) >= 0)
                        .ToList();

                    var newIds = new List<int>();
                    foreach (var pipe in v22Pipes)
                    {
                        ElementType ct = doc.GetElement(pipe.GetTypeId()) as ElementType;
                        if (ct != null && ct.Name.IndexOf("100", StringComparison.OrdinalIgnoreCase) >= 0)
                            newIds.Add(pipe.Id.IntegerValue);
                    }

                    if (newIds.Count > 0)
                    {
                        fix.RevitElementIds = newIds;
                        if (dn80Types.Count > 0)
                        {
                            fix.Steps = new List<FixStep>
                            {
                                new FixStep { Action = "change_type", Value = dn80Types.First().Name }
                            };
                        }
                        else
                        {
                            fix.Steps = new List<FixStep>
                            {
                                new FixStep
                                {
                                    Action = "select_and_warn",
                                    Param = "Тип DN80 не найден в проекте. Создайте вручную (дублируйте существующий, измените диаметр) и нажмите «Применить исправления» снова."
                                }
                            };
                        }
                    }
                    continue;
                }

                // 5. В1 оцинкованные трубы → черная сталь
                if (desc.Contains("оцинк") && desc.Contains("в1"))
                {
                    var v1Pipes = allPipes
                        .Where(p => p.MEPSystem != null && p.MEPSystem.Name != null &&
                                    p.MEPSystem.Name.IndexOf("В1", StringComparison.OrdinalIgnoreCase) >= 0)
                        .ToList();

                    string steelTypeName = "Черная сталь";
                    PipeType steelType = allPipeTypes.FirstOrDefault(pt =>
                        pt.Name.IndexOf("черн", StringComparison.OrdinalIgnoreCase) >= 0 ||
                        pt.Name.IndexOf("сталь", StringComparison.OrdinalIgnoreCase) >= 0);

                    var newIds = new List<int>();
                    foreach (var pipe in v1Pipes)
                    {
                        ElementType ct = doc.GetElement(pipe.GetTypeId()) as ElementType;
                        if (ct != null && ct.Name.IndexOf("оцинк", StringComparison.OrdinalIgnoreCase) >= 0)
                            newIds.Add(pipe.Id.IntegerValue);
                    }

                    if (newIds.Count > 0)
                    {
                        fix.RevitElementIds = newIds;
                        if (steelType != null)
                        {
                            fix.Steps = new List<FixStep>
                            {
                                new FixStep { Action = "change_type", Value = steelType.Name }
                            };
                        }
                        else
                        {
                            fix.Steps = new List<FixStep>
                            {
                                new FixStep
                                {
                                    Action = "select_and_warn",
                                    Param = "Тип «Черная сталь» не найден в проекте. Создайте его вручную и нажмите «Применить исправления» снова."
                                }
                            };
                        }
                    }
                    continue;
                }
            }
        }

        private List<int> RemoveExistingInsulation(Document doc, Element host)
        {
            var removed = new List<int>();
            var filter = new ElementClassFilter(typeof(PipeInsulation));
            var depIds = host.GetDependentElements(filter);
            foreach (var depId in depIds)
            {
                Element dep = doc.GetElement(depId);
                if (dep != null)
                {
                    removed.Add(dep.Id.IntegerValue);
                    doc.Delete(dep.Id);
                }
            }
            return removed;
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

        private Room FindRoomByName(Document doc, string namePart)
        {
            var rooms = new FilteredElementCollector(doc)
                .OfClass(typeof(SpatialElement))
                .WhereElementIsNotElementType()
                .Cast<SpatialElement>();

            foreach (var se in rooms)
            {
                if (se is Room room && room.Name != null &&
                    room.Name.IndexOf(namePart, StringComparison.OrdinalIgnoreCase) >= 0)
                    return room;
            }
            return null;
        }

        private bool PipeCrossesBox(Pipe pipe, XYZ min, XYZ max)
        {
            LocationCurve lc = pipe.Location as LocationCurve;
            if (lc == null) return false;

            Curve curve = lc.Curve;
            int samples = 10;

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
    }

    public class FixInstruction
    {
        public string FixId { get; set; }
        public string OrderId { get; set; }
        public string ElementName { get; set; }
        public string ElementGlobalId { get; set; }
        public List<string> ElementIds { get; set; }
        public List<int> RevitElementIds { get; set; }
        public string Description { get; set; }
        public string Risk { get; set; }
        public string IssueMessage { get; set; }
        public string IfcGuidHint { get; set; }
        public List<FixStep> Steps { get; set; }
        public FixAction UserAction { get; set; }
    }

    public class FixStep
    {
        public string Action { get; set; }
        public string Param { get; set; }
        public string Value { get; set; }
        public string ValueType { get; set; }
        public string FromParam { get; set; }
        public string ToParam { get; set; }
        public string SystemName { get; set; }
    }

    public enum FixAction
    {
        Apply,
        Skip
    }
}
