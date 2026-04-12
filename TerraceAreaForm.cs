using System;
using System.Windows.Forms;
using System.Linq;

namespace RevitExtension
{
    public partial class TerraceAreaForm : Form
    {
        private TextBox keywordsTextBox;
        private Button okButton;
        private Button cancelButton;

        public TerraceAreaForm()
        {
            InitializeComponent();
        }

        private void InitializeComponent()
        {
            this.Text = "Расчёт площади террас";
            this.Size = new System.Drawing.Size(450, 250);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.MaximizeBox = false;
            this.MinimizeBox = false;

            var label = new Label
            {
                Text = "Ключевые слова для поиска террас:\n(через запятую, например: терраса, лоджия, балкон)",
                Location = new System.Drawing.Point(15, 15),
                Size = new System.Drawing.Size(400, 50),
                AutoSize = false
            };
            this.Controls.Add(label);

            keywordsTextBox = new TextBox
            {
                Text = "терраса, лоджия, балкон, terrace, balcony",
                Location = new System.Drawing.Point(15, 75),
                Size = new System.Drawing.Size(400, 25),
                Multiline = false
            };
            this.Controls.Add(keywordsTextBox);

            var hintLabel = new Label
            {
                Text = "Поиск выполняется по названию помещения на выбранном виде.",
                Location = new System.Drawing.Point(15, 110),
                Size = new System.Drawing.Size(400, 20),
                ForeColor = System.Drawing.Color.Gray,
                AutoSize = false
            };
            this.Controls.Add(hintLabel);

            okButton = new Button
            {
                Text = "Найти",
                Location = new System.Drawing.Point(225, 150),
                Size = new System.Drawing.Size(90, 30),
                DialogResult = DialogResult.OK
            };
            okButton.Click += OkButton_Click;
            this.Controls.Add(okButton);

            cancelButton = new Button
            {
                Text = "Отмена",
                Location = new System.Drawing.Point(325, 150),
                Size = new System.Drawing.Size(90, 30),
                DialogResult = DialogResult.Cancel
            };
            this.Controls.Add(cancelButton);

            this.AcceptButton = okButton;
            this.CancelButton = cancelButton;
        }

        private void OkButton_Click(object sender, EventArgs e)
        {
            this.DialogResult = DialogResult.OK;
            this.Close();
        }

        public string[] GetKeywords()
        {
            return keywordsTextBox.Text
                .Split(new[] { ',', ';', '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(k => k.Trim())
                .Where(k => !string.IsNullOrEmpty(k))
                .ToArray();
        }
    }
}
