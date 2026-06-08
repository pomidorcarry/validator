using System;
using System.Collections.Generic;
using System.Drawing;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    public class AnalyzeResultForm : Form
    {
        private static readonly Color DarkBg = Color.FromArgb(11, 9, 20);
        private static readonly Color DarkPanel = Color.FromArgb(18, 16, 24);
        private static readonly Color DarkBorder = Color.FromArgb(42, 32, 48);
        private static readonly Color TextMain = Color.FromArgb(224, 220, 232);
        private static readonly Color TextSec = Color.FromArgb(136, 128, 160);
        private static readonly Color Accent = Color.FromArgb(139, 92, 246);
        private static readonly Color Error = Color.FromArgb(255, 107, 107);
        private static readonly Color Success = Color.FromArgb(52, 211, 153);

        private readonly List<FixInstruction> _fixes;
        private FlowLayoutPanel _fixesPanel;
        private Button _applyBtn;
        private Button _cancelBtn;

        public AnalyzeResultForm(List<FixInstruction> fixes)
        {
            _fixes = fixes;
            InitializeComponent();
        }

        private void InitializeComponent()
        {
            Text = "Результаты анализа — Lynx";
            Width = 720;
            Height = 560;
            StartPosition = FormStartPosition.CenterParent;
            MinimizeBox = false;
            MaximizeBox = false;
            BackColor = DarkBg;
            ForeColor = TextMain;

            var header = new Panel
            {
                Height = 70,
                Dock = DockStyle.Top,
                BackColor = DarkPanel,
            };

            var titleLabel = new Label
            {
                Text = $"Анализ модели завершён. Найдено проблем: {_fixes.Count}",
                Font = new Font("Segoe UI", 12, FontStyle.Bold),
                ForeColor = TextMain,
                Left = 16,
                Top = 12,
                Width = 500,
                Height = 22,
                BackColor = Color.Transparent,
            };

            var subtitleLabel = new Label
            {
                Text = "Проблемы будут исправлены после нажатия «Применить исправления» в главном окне",
                Font = new Font("Segoe UI", 9),
                ForeColor = TextSec,
                Left = 16,
                Top = 38,
                Width = 600,
                Height = 18,
                BackColor = Color.Transparent,
            };

            header.Controls.Add(titleLabel);
            header.Controls.Add(subtitleLabel);

            var headerLine = new Label
            {
                Dock = DockStyle.Top,
                Height = 1,
                BackColor = DarkBorder,
            };

            _fixesPanel = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true,
                Padding = new Padding(14, 8, 14, 14),
                FlowDirection = FlowDirection.TopDown,
                WrapContents = false,
                BackColor = DarkBg,
            };

            var bottomPanel = new Panel
            {
                Height = 50,
                Dock = DockStyle.Bottom,
                BackColor = DarkPanel,
                Padding = new Padding(12),
            };

            _applyBtn = new Button
            {
                Text = "Сформировать приказы",
                Width = 200,
                Height = 32,
                Left = bottomPanel.Width - 310,
                Top = 9,
                Anchor = AnchorStyles.Right,
                FlatStyle = FlatStyle.Flat,
                BackColor = Accent,
                ForeColor = Color.White,
                Font = new Font("Segoe UI", 9, FontStyle.Bold),
                Cursor = Cursors.Hand,
            };
            _applyBtn.FlatAppearance.BorderSize = 0;
            _applyBtn.Click += (s, e) => { DialogResult = DialogResult.OK; Close(); };

            _cancelBtn = new Button
            {
                Text = "Отмена",
                Width = 90,
                Height = 32,
                Left = bottomPanel.Width - 100,
                Top = 9,
                Anchor = AnchorStyles.Right,
                FlatStyle = FlatStyle.Flat,
                BackColor = DarkPanel,
                ForeColor = TextMain,
                Cursor = Cursors.Hand,
            };
            _cancelBtn.FlatAppearance.BorderColor = DarkBorder;
            _cancelBtn.Click += (s, e) => { DialogResult = DialogResult.Cancel; Close(); };

            bottomPanel.Controls.Add(_applyBtn);
            bottomPanel.Controls.Add(_cancelBtn);

            Controls.Add(_fixesPanel);
            Controls.Add(headerLine);
            Controls.Add(header);
            Controls.Add(bottomPanel);

            LoadFixes();
        }

        private void LoadFixes()
        {
            _fixesPanel.Controls.Clear();
            int cardWidth = _fixesPanel.Width - 36;

            foreach (var fix in _fixes)
            {
                int stepCount = fix.Steps?.Count ?? 0;
                int cardH = 100 + stepCount * 22;
                var card = new Panel
                {
                    Width = cardWidth,
                    Height = cardH,
                    Margin = new Padding(0, 0, 0, 8),
                    BackColor = DarkPanel,
                };

                card.Paint += (s, e) =>
                {
                    var c = s as Panel;
                    if (c == null) return;
                    using (var pen = new Pen(DarkBorder))
                        e.Graphics.DrawRectangle(pen, 0, 0, c.Width - 1, c.Height - 1);
                };

                var riskColor = fix.Risk == "low" ? Success :
                                fix.Risk == "high" ? Error : Accent;

                var riskBadge = new Label
                {
                    Text = (fix.Risk ?? "medium").ToUpper(),
                    Left = 12,
                    Top = 10,
                    Width = 56,
                    Height = 18,
                    Font = new Font("Segoe UI", 7, FontStyle.Bold),
                    ForeColor = riskColor,
                    BackColor = Color.Transparent,
                };

                var descLabel = new Label
                {
                    Text = fix.Description ?? "",
                    Left = 76,
                    Top = 8,
                    Width = cardWidth - 90,
                    Height = 20,
                    Font = new Font("Segoe UI", 9, FontStyle.Bold),
                    ForeColor = TextMain,
                    BackColor = Color.Transparent,
                };

                var issueLabel = new Label
                {
                    Text = fix.IssueMessage ?? "",
                    Left = 76,
                    Top = 28,
                    Width = cardWidth - 90,
                    Height = 18,
                    Font = new Font("Segoe UI", 8),
                    ForeColor = TextSec,
                    BackColor = Color.Transparent,
                };

                var elemLabel = new Label
                {
                    Text = $"Элемент: {fix.ElementName}" +
                           (fix.RevitElementIds != null && fix.RevitElementIds.Count > 0
                               ? $" | Revit ID: {string.Join(", ", fix.RevitElementIds)}" : ""),
                    Left = 76,
                    Top = 46,
                    Width = cardWidth - 90,
                    Height = 16,
                    Font = new Font("Segoe UI", 7),
                    ForeColor = TextSec,
                    BackColor = Color.Transparent,
                };

                card.Controls.Add(riskBadge);
                card.Controls.Add(descLabel);
                card.Controls.Add(issueLabel);
                card.Controls.Add(elemLabel);

                int stepTop = 66;
                if (fix.Steps != null)
                {
                    var stepsHeader = new Label
                    {
                        Text = "Шаги исправления:",
                        Left = 76,
                        Top = stepTop,
                        Width = cardWidth - 90,
                        Height = 16,
                        Font = new Font("Segoe UI", 7, FontStyle.Italic),
                        ForeColor = Accent,
                        BackColor = Color.Transparent,
                    };
                    card.Controls.Add(stepsHeader);
                    stepTop += 18;

                    foreach (var step in fix.Steps)
                    {
                        string stepText = step.Action switch
                        {
                            "change_type" => $"Сменить тип на: {step.Value}",
                            "change_insulation" => $"Сменить изоляцию на {step.Value} мм",
                            "select_and_warn" => "Выделить и показать предупреждение",
                            _ => $"{step.Action}: {step.Param} = {step.Value}",
                        };

                        var stepLabel = new Label
                        {
                            Text = $"  → {stepText}",
                            Left = 76,
                            Top = stepTop,
                            Width = cardWidth - 90,
                            Height = 18,
                            Font = new Font("Segoe UI", 8),
                            ForeColor = TextSec,
                            BackColor = Color.Transparent,
                        };
                        card.Controls.Add(stepLabel);
                        stepTop += 20;
                    }
                }

                _fixesPanel.Controls.Add(card);
            }
        }
    }
}
