#nullable enable
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    [Transaction(TransactionMode.Manual)]
    public class ShowChatCommand : IExternalCommand
    {
        private static ChatWindow? _window;

        public Result Execute(
            ExternalCommandData commandData,
            ref string message,
            ElementSet elements)
        {
            try
            {
                if (_window == null || _window.IsDisposed)
                {
                    _window = new ChatWindow();
                    _window.FormClosed += (_, _) => _window = null;
                    _window.Show();
                }
                else
                {
                    if (_window.WindowState == FormWindowState.Minimized)
                    {
                        _window.WindowState = FormWindowState.Normal;
                    }

                    _window.Activate();
                }
            }
            catch (System.Exception ex)
            {
                TaskDialog.Show("LYNX Assistant", ex.ToString());
            }

            return Result.Succeeded;
        }
    }
}
