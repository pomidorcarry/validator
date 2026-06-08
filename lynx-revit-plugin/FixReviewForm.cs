using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    public class FixReviewForm : Form
    {
        private FlowLayoutPanel _fixPanel;
        private Button _applyBtn;
        private Button _cancelBtn;
        private List<FixInstruction> _fixes;
        private Dictionary<string, CheckBox> _checkboxes;

        public FixReviewForm(List<FixInstruction> fixes)
        {
            _fixes = fixes;
            _checkboxes = new Dictionary<string, CheckBox>();
            InitializeComponent();
            LoadFixes();
        }

        private void InitializeComponent()
        {
            this.Text = "Применить исправления — Lynx";
            this.Width = 650;
            this.Height = 500;
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimumSize = new Size(500, 400);

            var header = new Label
            {
                Text = $"Найдено исправлений: {_fixes.Count}",
                Font = new Font("Segoe UI", 12, FontStyle.Bold),
                Dock = DockStyle.Top,
                Padding = new Padding(12, 12, 12, 4),
                Height = 40,
            };

            _fixPanel = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true,
                Padding = new Padding(12, 4, 12, 4),
                FlowDirection = FlowDirection.TopDown,
                WrapContents = false,
            };

            var btnPanel = new Panel
            {
                Dock = DockStyle.Bottom,
                Height = 50,
                Padding = new Padding(12),
            };

            _applyBtn = new Button
            {
                Text = "Применить выбранные",
                Width = 180,
                Height = 32,
                Left = btnPanel.Width - 280,
                Top = 10,
                Anchor = AnchorStyles.Right,
            };
            _applyBtn.Click += ApplyBtn_Click;

            _cancelBtn = new Button
            {
                Text = "Отмена",
                Width = 80,
                Height = 32,
                Left = btnPanel.Width - 90,
                Top = 10,
                Anchor = AnchorStyles.Right,
            };
            _cancelBtn.Click += (s, e) => { this.DialogResult = DialogResult.Cancel; this.Close(); };

            btnPanel.Controls.Add(_applyBtn);
            btnPanel.Controls.Add(_cancelBtn);

            this.Controls.Add(_fixPanel);
            this.Controls.Add(btnPanel);
            this.Controls.Add(header);
        }

        private void LoadFixes()
        {
            _fixPanel.Controls.Clear();
            _checkboxes.Clear();

            var grouped = _fixes
                .GroupBy(f => f.OrderId ?? "Без приказа")
                .ToList();

            foreach (var group in grouped)
            {
                var orderHeader = new Label
                {
                    Text = $"📋 Приказ: {group.Key}  |  Исправлений: {group.Count()}",
                    Font = new Font("Segoe UI", 10, FontStyle.Bold),
                    ForeColor = Color.FromArgb(139, 92, 246),
                    Width = _fixPanel.Width - 30,
                    Height = 28,
                    Margin = new Padding(0, 8, 0, 4),
                };

                _fixPanel.Controls.Add(orderHeader);

                foreach (var fix in group)
                {
                    int cardH = 90;
                    if (fix.Steps != null && fix.Steps.Count > 0) cardH += 18;

                    var card = new Panel
                    {
                        Width = _fixPanel.Width - 30,
                        Height = cardH,
                        Margin = new Padding(0, 0, 0, 6),
                        BorderStyle = BorderStyle.FixedSingle,
                    };

                    var cb = new CheckBox
                    {
                        Text = "",
                        Checked = true,
                        Left = 8,
                        Top = 8,
                        Width = 20,
                        Height = 20,
                    };
                    _checkboxes[fix.FixId] = cb;

                    int labelTop = 8;

                    var riskColor = fix.Risk == "low" ? Color.Green :
                                    fix.Risk == "high" ? Color.Red : Color.Orange;

                    var riskLabel = new Label
                    {
                        Text = fix.Risk?.ToUpper() ?? "MEDIUM",
                        Left = 32,
                        Top = labelTop,
                        Width = 60,
                        Height = 20,
                        Font = new Font("Segoe UI", 8, FontStyle.Bold),
                        ForeColor = riskColor,
                    };
                    card.Controls.Add(riskLabel);

                    var descLabel = new Label
                    {
                        Text = fix.Description ?? "",
                        Left = 96,
                        Top = labelTop,
                        Width = card.Width - 110,
                        Height = 20,
                        Font = new Font("Segoe UI", 9),
                    };
                    card.Controls.Add(descLabel);
                    labelTop += 22;

                    // Element name
                    string elemName = fix.ElementName ?? "(без имени)";
                    var nameLabel = new Label
                    {
                        Text = "Элемент: " + elemName,
                        Left = 32,
                        Top = labelTop,
                        Width = card.Width - 50,
                        Height = 16,
                        Font = new Font("Segoe UI", 9),
                        ForeColor = Color.Gray,
                    };
                    card.Controls.Add(nameLabel);
                    labelTop += 18;

                    // Global IFC ID + Revit ID
                    string globalId = fix.ElementGlobalId ?? "";
                    bool hasRevitIds = fix.RevitElementIds != null && fix.RevitElementIds.Count > 0;
                    string globalText = !string.IsNullOrEmpty(globalId) ? globalId : "(нет)";

                    var globalLabel = new Label
                    {
                        Text = "IFC GUID: " + globalText,
                        Left = 32,
                        Top = labelTop,
                        Width = card.Width - 50,
                        Height = 16,
                        Font = new Font("Segoe UI", 8, FontStyle.Italic),
                        ForeColor = Color.FromArgb(100, 100, 130),
                    };
                    card.Controls.Add(globalLabel);
                    labelTop += 16;

                    if (hasRevitIds)
                    {
                        var revitLabel = new Label
                        {
                            Text = "Revit ID: " + string.Join(", ", fix.RevitElementIds),
                            Left = 32,
                            Top = labelTop,
                            Width = card.Width - 50,
                            Height = 16,
                            Font = new Font("Segoe UI", 8, FontStyle.Bold),
                            ForeColor = Color.FromArgb(52, 211, 153),
                        };
                        card.Controls.Add(revitLabel);
                        labelTop += 18;
                    }

                    // Steps info
                    if (fix.Steps != null && fix.Steps.Count > 0)
                    {
                        var actions = string.Join(", ", fix.Steps.Select(s => s.Action));
                        var stepsLabel2 = new Label
                        {
                            Text = "Шаги: " + actions,
                            Left = 32,
                            Top = labelTop,
                            Width = card.Width - 50,
                            Height = 16,
                            Font = new Font("Segoe UI", 8),
                            ForeColor = Color.Gray,
                        };
                        card.Controls.Add(stepsLabel2);
                    }

                    card.Controls.Add(cb);

                    _fixPanel.Controls.Add(card);
                }
            }
        }

        private void ApplyBtn_Click(object sender, EventArgs e)
        {
            foreach (var fix in _fixes)
            {
                bool checked_ = _checkboxes.ContainsKey(fix.FixId) && _checkboxes[fix.FixId].Checked;
                fix.UserAction = checked_ ? FixAction.Apply : FixAction.Skip;
            }

            this.DialogResult = DialogResult.OK;
            this.Close();
        }
    }
}
