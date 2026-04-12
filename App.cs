using Autodesk.Revit.UI;
using Autodesk.Revit.Attributes;
using System.Collections.Generic;
using System.IO;
using System.Reflection;

namespace RevitExtension
{
    [Regeneration(RegenerationOption.Manual)]
    public class App : IExternalApplication
    {
        public Result OnStartup(UIControlledApplication app)
        {
            string tabName = "Lynx";

            try
            {
                app.CreateRibbonTab(tabName);
            }
            catch
            {
            }

            var panel = app.CreateRibbonPanel(tabName, "Инструменты");

            var assemblyPath = Assembly.GetExecutingAssembly().Location;

            var terraceButton = new PushButtonData(
                "TerraceArea",
                "Площадь террас",
                assemblyPath,
                "RevitExtension.TerraceAreaCommand")
            {
                ToolTip = "Расчёт площади террас на выбранном виде"
            };

            panel.AddItem(terraceButton);

            return Result.Succeeded;
        }

        public Result OnShutdown(UIControlledApplication app)
        {
            return Result.Succeeded;
        }
    }
}
