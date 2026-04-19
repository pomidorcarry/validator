using Autodesk.Revit.UI;
using Autodesk.Revit.Attributes;
using System.Reflection;

namespace LynxRevitPlugin
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

            var panel = app.CreateRibbonPanel(tabName, "BIM Проверка");

            var assemblyPath = Assembly.GetExecutingAssembly().Location;

            var exportIfcButton = new PushButtonData(
                "ExportIFC",
                "Экспорт в Lynx",
                assemblyPath,
                "LynxRevitPlugin.ExportIfcCommand")
            {
                ToolTip = "Экспортировать модель IFC и отправить на сервер Lynx"
            };

            var settingsButton = new PushButtonData(
                "Settings",
                "Настройки",
                assemblyPath,
                "LynxRevitPlugin.SettingsCommand")
            {
                ToolTip = "Настроить подключение к серверу Lynx"
            };

            panel.AddItem(exportIfcButton);
            panel.AddItem(settingsButton);

            return Result.Succeeded;
        }

        public Result OnShutdown(UIControlledApplication app)
        {
            return Result.Succeeded;
        }
    }
}