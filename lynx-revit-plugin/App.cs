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
            string tabName = "LYNX AI";

            try
            {
                app.CreateRibbonTab(tabName);
            }
            catch
            {
            }

            var assemblyPath = Assembly.GetExecutingAssembly().Location;

            // ── Panel 1: BIM Проверка ──
            var validationPanel = app.CreateRibbonPanel(tabName, "BIM Проверка");

            var exportIfcButton = new PushButtonData(
                "ExportIFC",
                "Экспорт в Lynx",
                assemblyPath,
                "LynxRevitPlugin.ExportIfcCommand")
            {
                ToolTip = "Экспортировать модель IFC и отправить на сервер Lynx"
            };
            validationPanel.AddItem(exportIfcButton);

            var settingsButton = new PushButtonData(
                "Settings",
                "Настройки",
                assemblyPath,
                "LynxRevitPlugin.SettingsCommand")
            {
                ToolTip = "Настроить подключение к серверу Lynx"
            };
            validationPanel.AddItem(settingsButton);

            var chatButton = new PushButtonData(
                "Chat",
                "AI Ассистент",
                assemblyPath,
                "LynxRevitPlugin.ShowChatCommand")
            {
                ToolTip = "Открыть AI-чат"
            };
            validationPanel.AddItem(chatButton);

            // ── Panel 2: Приказы на изменения ──
            var ordersPanel = app.CreateRibbonPanel(tabName, "Приказы на изменения");

            var ordersButton = new PushButtonData(
                "Orders",
                "Приказы",
                assemblyPath,
                "LynxRevitPlugin.OrdersCommand")
            {
                ToolTip = "Просмотреть приказы на внесение изменений в модель"
            };
            ordersPanel.AddItem(ordersButton);

            var applyFixesButton = new PushButtonData(
                "ApplyFixes",
                "Применить исправления",
                assemblyPath,
                "LynxRevitPlugin.ApplyFixesCommand")
            {
                ToolTip = "Применить исправления из утверждённых приказов"
            };
            ordersPanel.AddItem(applyFixesButton);

            return Result.Succeeded;
        }

        public Result OnShutdown(UIControlledApplication app)
        {
            return Result.Succeeded;
        }
    }
}