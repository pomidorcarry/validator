using System;
using System.IO;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace LynxRevitPlugin
{
    public class ChatWindow : Form
    {
        private WebView2 webView;

        public ChatWindow()
        {
            Text = "LYNX Assistant";
            Size = new System.Drawing.Size(450, 800);
            StartPosition = FormStartPosition.CenterScreen;

            webView = new WebView2
            {
                Dock = DockStyle.Fill
            };
            Controls.Add(webView);

            Shown += ChatWindow_Shown;
        }

        private async void ChatWindow_Shown(object sender, EventArgs e)
        {
            try
            {
                string userDataFolder = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "LynxRevitPlugin",
                    "WebView2");

                Directory.CreateDirectory(userDataFolder);

                CoreWebView2Environment environment =
                    await CoreWebView2Environment.CreateAsync(null, userDataFolder);

                await webView.EnsureCoreWebView2Async(environment);
                webView.Source = new Uri("https://web-tan-ten-43.vercel.app");
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    ex.ToString(),
                    "LYNX Assistant error",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }
    }
}
