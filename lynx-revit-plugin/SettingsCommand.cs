using Autodesk.Revit.UI;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;

namespace LynxRevitPlugin
{
    [Transaction(TransactionMode.ReadOnly)]
    public class SettingsCommand : IExternalCommand
    {
        public Result Execute(
            ExternalCommandData commandData,
            ref string message,
            ElementSet elements)
        {
            SettingsForm settingsForm = new SettingsForm();
            settingsForm.ShowDialog();
            return Result.Succeeded;
        }
    }
}