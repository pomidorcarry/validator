using System;
using System.Threading;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    public class ProgressFormHandle
    {
        private ExportProgressForm _form;
        private Thread _thread;

        public void Show()
        {
            var ready = new ManualResetEvent(false);
            _thread = new Thread(() =>
            {
                _form = new ExportProgressForm();
                _form.FormClosed += (s, e) => Application.ExitThread();
                _form.Show();
                ready.Set();
                Application.Run();
            });
            _thread.SetApartmentState(ApartmentState.STA);
            _thread.IsBackground = true;
            _thread.Name = "LynxProgressForm";
            _thread.Start();
            ready.WaitOne(5000);
        }

        public void SetStatus(string text) => Exec(f => f.SetStatus(text));
        public void SetProgress(int percent) => Exec(f => f.SetProgress(percent));
        public void SetCompleted(bool success, string message) => Exec(f => f.SetCompleted(success, message));
        public bool IsCompleted => _form != null && _form.IsCompleted;

        public void Close()
        {
            if (_form != null && !_form.IsDisposed)
            {
                try { _form.Invoke(new Action(() => _form.Close())); } catch { }
            }
        }

        private void Exec(Action<ExportProgressForm> action)
        {
            if (_form == null || _form.IsDisposed) return;
            try
            {
                if (_form.InvokeRequired)
                    _form.Invoke(new Action(() => action(_form)));
                else
                    action(_form);
            }
            catch
            {
            }
        }
    }
}
