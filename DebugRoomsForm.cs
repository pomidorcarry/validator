using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;

namespace RevitExtension
{
    public class DebugRoomsForm : Form
    {
        private DataGridView dataGridView;
        private Button closeButton;
        private List<RoomDebugInfo> _rooms;
        private List<string> _keywords;

        public DebugRoomsForm(List<RoomDebugInfo> rooms, List<string> keywords)
        {
            _rooms = rooms;
            _keywords = keywords;
            InitializeComponent();
            LoadData();
        }

        private void InitializeComponent()
        {
            this.Text = "Отладка - Все помещения на видах";
            this.Size = new System.Drawing.Size(900, 600);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.MinimizeBox = true;

            var label = new Label
            {
                Text = $"Всего помещений: {_rooms.Count} | Террас: {_rooms.Count(r => r.IsTerrace)}",
                Location = new System.Drawing.Point(15, 10),
                AutoSize = true,
                Font = new Font(this.Font, FontStyle.Bold)
            };
            this.Controls.Add(label);

            var hintLabel = new Label
            {
                Text = "Зелёным выделены террасы, удовлетворяющие ключевым словам: " + string.Join(", ", _keywords),
                Location = new System.Drawing.Point(15, 35),
                AutoSize = true,
                ForeColor = Color.Green
            };
            this.Controls.Add(hintLabel);

            dataGridView = new DataGridView
            {
                Location = new System.Drawing.Point(15, 60),
                Size = new System.Drawing.Size(850, 470),
                ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.AutoSize,
                AllowUserToAddRows = false,
                AllowUserToDeleteRows = false,
                ReadOnly = true,
                SelectionMode = DataGridViewSelectionMode.FullRowSelect,
                MultiSelect = false,
                AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
                RowHeadersVisible = true,
                RowHeadersWidth = 30
            };
            this.Controls.Add(dataGridView);

            closeButton = new Button
            {
                Text = "Закрыть",
                Location = new System.Drawing.Point(765, 540),
                Size = new System.Drawing.Size(100, 30),
                DialogResult = DialogResult.OK
            };
            closeButton.Click += (s, e) => this.Close();
            this.Controls.Add(closeButton);

            this.AcceptButton = closeButton;
        }

        private void LoadData()
        {
            dataGridView.Columns.Add("ViewName", "Вид");
            dataGridView.Columns.Add("LevelName", "Уровень");
            dataGridView.Columns.Add("RoomName", "Название помещения");
            dataGridView.Columns.Add("AreaM2", "Площадь, м²");
            dataGridView.Columns.Add("LinkInfo", "Файл");

            foreach (var room in _rooms.OrderBy(r => r.ViewName).ThenBy(r => r.RoomName))
            {
                var index = dataGridView.Rows.Add(
                    room.ViewName,
                    room.LevelName,
                    room.RoomName,
                    room.AreaM2.ToString("F2"),
                    room.LinkInfo);

                if (room.IsTerrace)
                {
                    dataGridView.Rows[index].DefaultCellStyle.BackColor = Color.LightGreen;
                    dataGridView.Rows[index].HeaderCell.Value = "✓";
                }
                else
                {
                    dataGridView.Rows[index].HeaderCell.Value = "";
                }
            }
        }
    }
}
