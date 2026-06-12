using System;
using System.IO;
using System.Windows;
using Microsoft.Web.WebView2.Core;

namespace LynxRevitPlugin
{
    public partial class ChatWindow : Window
    {
        public ChatWindow()
        {
            InitializeComponent();
            Loaded += ChatWindow_Loaded;
        }

        private async void ChatWindow_Loaded(object sender, RoutedEventArgs e)
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
                    MessageBoxButton.OK,
                    MessageBoxImage.Error
                );
            }
        }
    }
}
