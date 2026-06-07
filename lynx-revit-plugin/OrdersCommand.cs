using Autodesk.Revit.UI;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using System;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    [Transaction(TransactionMode.Manual)]
    public class OrdersCommand : IExternalCommand
    {
        public Result Execute(
            ExternalCommandData commandData,
            ref string message,
            ElementSet elements)
        {
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

            using (var form = new OrdersForm(settings.ServerUrl, settings.ProjectId))
            {
                form.ShowDialog();
            }

            return Result.Succeeded;
        }
    }
}
