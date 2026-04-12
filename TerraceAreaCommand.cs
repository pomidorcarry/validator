using Autodesk.Revit.UI;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Architecture;
using System.Collections.Generic;
using System.Linq;

namespace RevitExtension
{
    [Transaction(TransactionMode.ReadOnly)]
    public class TerraceAreaCommand : IExternalCommand
    {
        public Result Execute(
            ExternalCommandData commandData,
            ref string message,
            ElementSet elements)
        {
            var uiDoc = commandData.Application.ActiveUIDocument;
            var doc = uiDoc.Document;

            var form = new TerraceAreaForm();
            if (form.ShowDialog() != System.Windows.Forms.DialogResult.OK)
                return Result.Cancelled;

            var keywords = form.GetKeywords()
                .Select(k => k.ToLower().Trim())
                .Where(k => !string.IsNullOrEmpty(k))
                .ToList();

            if (keywords.Count == 0)
            {
                TaskDialog.Show("Ошибка", "Укажите хотя бы одно ключевое слово для поиска террас.");
                return Result.Failed;
            }

            var view = uiDoc.ActiveView;
            if (view == null || !(view is ViewPlan))
            {
                TaskDialog.Show("Ошибка", "Выберите вид плана этажа.");
                return Result.Failed;
            }

            var terraces = new List<TerraceInfo>();

            var roomCollector = new FilteredElementCollector(doc, view.Id)
                .OfCategory(BuiltInCategory.OST_Rooms)
                .WhereElementIsNotElementType();

            foreach (Room room in roomCollector)
            {
                var roomName = room.Name?.ToLower() ?? "";
                if (keywords.Any(k => roomName.Contains(k)))
                {
                    double areaM2 = room.Area * 0.092903;

                    terraces.Add(new TerraceInfo
                    {
                        Name = room.Name,
                        AreaM2 = areaM2,
                        Level = room.Level?.Name ?? "Неизвестно"
                    });
                }
            }

            if (terraces.Count == 0)
            {
                TaskDialog.Show("Результат", "Террасы не найдены.\n\nПроверьте ключевые слова или выберите правильный вид.");
                return Result.Succeeded;
            }

            var resultsForm = new TerraceResultsForm(terraces);
            resultsForm.ShowDialog();

            return Result.Succeeded;
        }
    }

    public class TerraceInfo
    {
        public string Name { get; set; }
        public double AreaM2 { get; set; }
        public string Level { get; set; }
    }
}
