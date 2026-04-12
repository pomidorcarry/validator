using System;
using System.Collections.Generic;
using System.Windows.Forms;
using System.Linq;

namespace RevitExtension
{
    public partial class TerraceResultsForm : Form
    {
        private DataGridView dataGridView;
        private Button closeButton;
        private List<TerraceInfo> _terraces;

        public TerraceResultsForm(List<TerraceInfo> terraces)
        {
            _terraces = terraces;
            InitializeComponent();
            LoadData();
        }

        private void InitializeComponent()
        {
            this.Text = "Площади террас";
            this.Size = new System.Drawing.Size(550, 400);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.MaximizeBox = true;
            this.MinimizeBox = false;

            var label = new Label
            {
                Text = $"Найдено террас: {_terraces.Count}",
                Location = new System.Drawing.Point(15, 10),
                AutoSize = true
            };
            this.Controls.Add(label);

            dataGridView = new DataGridView
            {
                Location = new System.Drawing.Point(15, 40),
                Size = new System.Drawing.Size(500, 280),
                ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.AutoSize,
                AllowUserToAddRows = false,
                AllowUserToDeleteRows = false,
                ReadOnly = true,
                SelectionMode = DataGridViewSelectionMode.FullRowSelect,
                MultiSelect = false,
                AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill
            };
            this.Controls.Add(dataGridView);

            closeButton = new Button
            {
                Text = "Закрыть",
                Location = new System.Drawing.Point(425, 330),
                Size = new System.Drawing.Size(90, 30),
                DialogResult = DialogResult.OK
            };
            closeButton.Click += (s, e) => this.Close();
            this.Controls.Add(closeButton);

            this.AcceptButton = closeButton;
        }

        private void LoadData()
        {
            var totalArea = _terraces.Sum(t => t.AreaM2);

            dataGridView.Columns.Add("Name", "Название");
            dataGridView.Columns.Add("Area", "Площадь, м²");
            dataGridView.Columns.Add("Level", "Уровень");

            foreach (var terrace in _terraces.OrderBy(t => t.Level).ThenBy(t => t.Name))
            {
                dataGridView.Rows.Add(
                    terrace.Name,
                    terrace.AreaM2.ToString("F2"),
                    terrace.Level);
            }

            dataGridView.Rows.Add(
                "━━━━━━━━━━━━━━━━━━",
                "━━━━━━━━━━━━━━━",
                "━━━━━━━━━━━");

            dataGridView.Rows.Add(
                $"ИТОГО ({_terraces.Count} шт.)",
                totalArea.ToString("F2"),
                "м²");
        }
    }
}
