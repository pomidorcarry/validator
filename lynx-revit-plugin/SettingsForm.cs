using System;
using System.IO;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    public class SettingsForm : Form
    {
        private TextBox serverUrlTextBox;
        private TextBox projectIdTextBox;
        private TextBox rulesetIdTextBox;
        private Button saveButton;
        private Button cancelButton;

        private const string CONFIG_FILE = "LynxSettings.txt";

        public string ServerUrl { get; private set; }
        public string ProjectId { get; private set; }
        public string RulesetId { get; private set; }

        public SettingsForm()
        {
            InitializeComponent();
            LoadSettings();
        }

        private void InitializeComponent()
        {
            this.Text = "Настройки Lynx";
            this.Width = 450;
            this.Height = 250;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.StartPosition = FormStartPosition.CenterParent;

            var serverUrlLabel = new Label { Text = "URL сервера:", Left = 20, Top = 20, Width = 100 };
            serverUrlTextBox = new TextBox { Left = 130, Top = 17, Width = 280 };
            serverUrlTextBox.Text = "http://localhost:8000";

            var projectIdLabel = new Label { Text = "Project ID:", Left = 20, Top = 60, Width = 100 };
            projectIdTextBox = new TextBox { Left = 130, Top = 57, Width = 280 };
            projectIdTextBox.Text = "default";

            var rulesetIdLabel = new Label { Text = "Ruleset ID:", Left = 20, Top = 100, Width = 100 };
            rulesetIdTextBox = new TextBox { Left = 130, Top = 97, Width = 280 };
            rulesetIdTextBox.Text = "default";

            saveButton = new Button { Text = "Сохранить", Left = 250, Top = 150, Width = 80 };
            saveButton.Click += SaveButton_Click;

            cancelButton = new Button { Text = "Отмена", Left = 340, Top = 150, Width = 80 };
            cancelButton.Click += (s, e) => { this.DialogResult = DialogResult.Cancel; this.Close(); };

            this.Controls.AddRange(new Control[] {
                serverUrlLabel, serverUrlTextBox,
                projectIdLabel, projectIdTextBox,
                rulesetIdLabel, rulesetIdTextBox,
                saveButton, cancelButton
            });
        }

        private void LoadSettings()
        {
            string configPath = GetConfigPath();
            if (File.Exists(configPath))
            {
                try
                {
                    var lines = File.ReadAllLines(configPath);
                    foreach (var line in lines)
                    {
                        var parts = line.Split('=');
                        if (parts.Length == 2)
                        {
                            switch (parts[0])
                            {
                                case "ServerUrl": serverUrlTextBox.Text = parts[1]; break;
                                case "ProjectId": projectIdTextBox.Text = parts[1]; break;
                                case "RulesetId": rulesetIdTextBox.Text = parts[1]; break;
                            }
                        }
                    }
                }
                catch { }
            }
        }

        private void SaveButton_Click(object sender, EventArgs e)
        {
            ServerUrl = serverUrlTextBox.Text;
            ProjectId = projectIdTextBox.Text;
            RulesetId = rulesetIdTextBox.Text;

            SaveSettings();
            this.DialogResult = DialogResult.OK;
            this.Close();
        }

        private void SaveSettings()
        {
            try
            {
                string configPath = GetConfigPath();
                string dir = Path.GetDirectoryName(configPath);
                if (!Directory.Exists(dir))
                    Directory.CreateDirectory(dir);

                var lines = new string[] {
                    $"ServerUrl={ServerUrl}",
                    $"ProjectId={ProjectId}",
                    $"RulesetId={RulesetId}"
                };
                File.WriteAllLines(configPath, lines);
            }
            catch { }
        }

        private string GetConfigPath()
        {
            string appDataPath = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            return Path.Combine(appDataPath, "Lynx", CONFIG_FILE);
        }

        public static SettingsData LoadSettingsData()
        {
            string configPath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "Lynx", CONFIG_FILE);

            if (!File.Exists(configPath))
            {
                return new SettingsData
                {
                    ServerUrl = "http://localhost:8000",
                    ProjectId = "default",
                    RulesetId = "default"
                };
            }

            try
            {
                var lines = File.ReadAllLines(configPath);
                var data = new SettingsData();
                foreach (var line in lines)
                {
                    var parts = line.Split('=');
                    if (parts.Length == 2)
                    {
                        switch (parts[0])
                        {
                            case "ServerUrl": data.ServerUrl = parts[1]; break;
                            case "ProjectId": data.ProjectId = parts[1]; break;
                            case "RulesetId": data.RulesetId = parts[1]; break;
                        }
                    }
                }
                return data;
            }
            catch
            {
                return new SettingsData
                {
                    ServerUrl = "http://localhost:8000",
                    ProjectId = "default",
                    RulesetId = "default"
                };
            }
        }
    }

    public class SettingsData
    {
        public string ServerUrl { get; set; }
        public string ProjectId { get; set; }
        public string RulesetId { get; set; }
    }
}