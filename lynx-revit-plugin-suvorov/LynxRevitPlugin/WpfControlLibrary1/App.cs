using System;
using System.Reflection;
using Autodesk.Revit.UI;

namespace LynxRevitPlugin
{
    public class App : IExternalApplication
    {
        public Result OnStartup(UIControlledApplication application)
        {
            string tabName = "LYNX AI";

            try
            {
                application.CreateRibbonTab(tabName);
            }
            catch
            {
            }

            RibbonPanel panel = application.CreateRibbonPanel(tabName, "Assistant");

            string assemblyPath = Assembly.GetExecutingAssembly().Location;

            PushButtonData buttonData = new PushButtonData(
                "LynxChatButton",
                "Открыть\nчат",
                assemblyPath,
                "LynxRevitPlugin.ShowChatCommand"
            );

            panel.AddItem(buttonData);

            return Result.Succeeded;
        }

        public Result OnShutdown(UIControlledApplication application)
        {
            return Result.Succeeded;
        }
    }
}
