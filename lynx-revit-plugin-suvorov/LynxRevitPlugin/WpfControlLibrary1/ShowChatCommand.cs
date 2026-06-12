using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using System.Windows.Interop;

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
                if (_window == null || !_window.IsVisible)
                {
                    _window = new ChatWindow();
                    new WindowInteropHelper(_window).Owner = commandData.Application.MainWindowHandle;
                    _window.Closed += (_, _) => _window = null;
                    _window.Show();
                }
                else
                {
                    if (_window.WindowState == System.Windows.WindowState.Minimized)
                    {
                        _window.WindowState = System.Windows.WindowState.Normal;
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
