using System;
using System.Collections.Generic;
using System.Windows.Forms;

namespace RevitExtension
{
    public partial class ViewSelectionForm : Form
    {
        private CheckedListBox checkedListBox;
        private Button selectAllButton;
        private Button deselectAllButton;
        private Button okButton;
        private Button cancelButton;
        private List<Autodesk.Revit.DB.ViewPlan> _views;
        private List<Autodesk.Revit.DB.ViewPlan> _selectedViews;

        public ViewSelectionForm(List<Autodesk.Revit.DB.ViewPlan> views)
        {
            _views = views;
            _selectedViews = new List<Autodesk.Revit.DB.ViewPlan>();
            InitializeComponent();
            LoadViews();
        }

        private void InitializeComponent()
        {
            this.Text = "Выбор видов для поиска";
            this.Size = new System.Drawing.Size(450, 500);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.MaximizeBox = false;
            this.MinimizeBox = false;

            var label = new Label
            {
                Text = "Выберите виды планов этажей:",
                Location = new System.Drawing.Point(15, 15),
                AutoSize = true
            };
            this.Controls.Add(label);

            checkedListBox = new CheckedListBox
            {
                Location = new System.Drawing.Point(15, 40),
                Size = new System.Drawing.Size(400, 350),
                CheckOnClick = true,
                ScrollAlwaysVisible = true
            };
            this.Controls.Add(checkedListBox);

            selectAllButton = new Button
            {
                Text = "Выбрать все",
                Location = new System.Drawing.Point(15, 400),
                Size = new System.Drawing.Size(100, 30)
            };
            selectAllButton.Click += SelectAllButton_Click;
            this.Controls.Add(selectAllButton);

            deselectAllButton = new Button
            {
                Text = "Снять выбор",
                Location = new System.Drawing.Point(125, 400),
                Size = new System.Drawing.Size(100, 30)
            };
            deselectAllButton.Click += DeselectAllButton_Click;
            this.Controls.Add(deselectAllButton);

            okButton = new Button
            {
                Text = "Далее",
                Location = new System.Drawing.Point(215, 450),
                Size = new System.Drawing.Size(100, 30),
                DialogResult = DialogResult.OK
            };
            this.Controls.Add(okButton);

            cancelButton = new Button
            {
                Text = "Отмена",
                Location = new System.Drawing.Point(325, 450),
                Size = new System.Drawing.Size(90, 30),
                DialogResult = DialogResult.Cancel
            };
            this.Controls.Add(cancelButton);

            this.AcceptButton = okButton;
            this.CancelButton = cancelButton;
        }

        private void LoadViews()
        {
            foreach (var view in _views)
            {
                var levelName = view.GenLevel?.Name ?? "";
                var displayName = $"{view.Name} ({levelName})";
                checkedListBox.Items.Add(displayName, true);
            }
        }

        private void SelectAllButton_Click(object sender, EventArgs e)
        {
            for (int i = 0; i < checkedListBox.Items.Count; i++)
            {
                checkedListBox.SetItemChecked(i, true);
            }
        }

        private void DeselectAllButton_Click(object sender, EventArgs e)
        {
            for (int i = 0; i < checkedListBox.Items.Count; i++)
            {
                checkedListBox.SetItemChecked(i, false);
            }
        }

        public List<Autodesk.Revit.DB.ViewPlan> GetSelectedViews()
        {
            _selectedViews.Clear();
            for (int i = 0; i < checkedListBox.Items.Count; i++)
            {
                if (checkedListBox.GetItemChecked(i))
                {
                    _selectedViews.Add(_views[i]);
                }
            }
            return _selectedViews;
        }
    }
}
