using System;
using System.Collections.Generic;
using System.Drawing;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    public class FixReportEntry
    {
        public string ElementName { get; set; }
        public string Description { get; set; }
        public bool Success { get; set; }
        public string RevitIds { get; set; }
        public string ErrorMessage { get; set; }
        public List<string> StepResults { get; set; }
    }

    public class FixResultForm : Form
    {
        private static readonly Color DarkBg = Color.FromArgb(11, 11, 28);
        private static readonly Color DarkSurface = Color.FromArgb(22, 22, 48);
        private static readonly Color PurplePrimary = Color.FromArgb(108, 99, 255);
        private static readonly Color PurpleLight = Color.FromArgb(179, 136, 255);
        private static readonly Color TextPrimary = Color.FromArgb(235, 235, 245);
        private static readonly Color TextMuted = Color.FromArgb(150, 150, 175);
        private static readonly Color GreenOk = Color.FromArgb(76, 175, 80);
        private static readonly Color RedError = Color.FromArgb(244, 67, 54);
        private static readonly Color DarkBorder = Color.FromArgb(40, 40, 80);

        private FlowLayoutPanel _resultsPanel;
        private Label _summaryLabel;
        private Label _statusIcon;
        private readonly int _applied;
        private readonly int _failed;
        private readonly List<FixReportEntry> _entries;

        public FixResultForm(int applied, int failed, List<FixReportEntry> entries)
        {
            _applied = applied;
            _failed = failed;
            _entries = entries ?? new List<FixReportEntry>();
            InitializeComponent();
        }

        private void InitializeComponent()
        {
            Width = 680;
            Height = 520;
            FormBorderStyle = FormBorderStyle.FixedSingle;
            StartPosition = FormStartPosition.CenterParent;
            MinimizeBox = false;
            MaximizeBox = false;
            Text = "Результат исправлений — Lynx";
            BackColor = DarkBg;
            ForeColor = TextPrimary;

            var headerPanel = new Panel
            {
                Height = 80,
                Dock = DockStyle.Top,
                BackColor = DarkSurface,
                Padding = new Padding(20, 14, 20, 10),
            };

            _statusIcon = new Label
            {
                Text = _failed > 0 ? "\u2716" : "\u2714",
                Font = new Font("Segoe UI", 28, FontStyle.Bold),
                ForeColor = _failed > 0 ? RedError : GreenOk,
                Left = 20,
                Top = 16,
                Width = 50,
                Height = 50,
                BackColor = Color.Transparent,
                TextAlign = ContentAlignment.MiddleCenter,
            };

            _summaryLabel = new Label
            {
                Text = $"Применено: {_applied}  |  Ошибок: {_failed}",
                Font = new Font("Segoe UI", 14, FontStyle.Bold),
                ForeColor = TextPrimary,
                Left = 80,
                Top = 18,
                Width = 400,
                Height = 24,
                BackColor = Color.Transparent,
            };

            var detailHint = new Label
            {
                Text = _failed > 0 ? "Некоторые исправления завершились с ошибкой. Подробности ниже." : "Все исправления успешно применены.",
                Font = new Font("Segoe UI", 9),
                ForeColor = TextMuted,
                Left = 80,
                Top = 46,
                Width = 500,
                Height = 18,
                BackColor = Color.Transparent,
            };

            headerPanel.Controls.Add(_statusIcon);
            headerPanel.Controls.Add(_summaryLabel);
            headerPanel.Controls.Add(detailHint);

            _resultsPanel = new FlowLayoutPanel
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
                BackColor = DarkSurface,
                Padding = new Padding(14, 8, 14, 8),
            };

            var closeBtn = new Button
            {
                Text = "Закрыть",
                Font = new Font("Segoe UI", 9, FontStyle.Bold),
                ForeColor = Color.White,
                BackColor = PurplePrimary,
                FlatStyle = FlatStyle.Flat,
                Width = 100,
                Height = 30,
                Cursor = Cursors.Hand,
            };
            closeBtn.FlatAppearance.BorderSize = 0;
            closeBtn.Click += (s, e) => Close();
            closeBtn.Left = bottomPanel.Width - closeBtn.Width - 14;
            closeBtn.Top = 10;
            closeBtn.Anchor = AnchorStyles.Right;

            bottomPanel.Controls.Add(closeBtn);

            Controls.Add(_resultsPanel);
            Controls.Add(headerPanel);
            Controls.Add(bottomPanel);

            LoadResults();

            Paint += (s, e) =>
            {
                using (var pen = new Pen(PurplePrimary, 3))
                    e.Graphics.DrawLine(pen, 0, 0, Width, 0);
            };
        }

        private void LoadResults()
        {
            _resultsPanel.Controls.Clear();
            int cardWidth = _resultsPanel.Width - 36;

            if (_entries.Count == 0)
            {
                var empty = new Label
                {
                    Text = "Нет результатов для отображения.",
                    Width = cardWidth,
                    Height = 60,
                    Font = new Font("Segoe UI", 10),
                    ForeColor = TextMuted,
                    BackColor = Color.Transparent,
                    TextAlign = ContentAlignment.MiddleCenter,
                };
                _resultsPanel.Controls.Add(empty);
                return;
            }

            foreach (var entry in _entries)
            {
                int stepCount = entry.StepResults?.Count ?? 0;
                int cardH = 70 + stepCount * 22;
                var card = new Panel
                {
                    Width = cardWidth,
                    Height = cardH,
                    Margin = new Padding(0, 0, 0, 8),
                    BackColor = DarkSurface,
                };

                card.Paint += (s, e) =>
                {
                    var c = s as Panel;
                    using (var pen = new Pen(DarkBorder))
                        e.Graphics.DrawRectangle(pen, 0, 0, c.Width - 1, c.Height - 1);
                };

                var icon = new Label
                {
                    Text = entry.Success ? "\u2714" : "\u2716",
                    Font = new Font("Segoe UI", 14, FontStyle.Bold),
                    ForeColor = entry.Success ? GreenOk : RedError,
                    Left = 10,
                    Top = 10,
                    Width = 24,
                    Height = 24,
                    BackColor = Color.Transparent,
                    TextAlign = ContentAlignment.MiddleCenter,
                };

                var nameLabel = new Label
                {
                    Text = entry.ElementName ?? "(без имени)",
                    Font = new Font("Segoe UI", 10, FontStyle.Bold),
                    ForeColor = TextPrimary,
                    Left = 40,
                    Top = 8,
                    Width = cardWidth - 60,
                    Height = 20,
                    BackColor = Color.Transparent,
                };

                var descLabel = new Label
                {
                    Text = entry.Description ?? "",
                    Font = new Font("Segoe UI", 9),
                    ForeColor = TextMuted,
                    Left = 40,
                    Top = 28,
                    Width = cardWidth - 60,
                    Height = 18,
                    BackColor = Color.Transparent,
                };

                card.Controls.Add(icon);
                card.Controls.Add(nameLabel);
                card.Controls.Add(descLabel);

                if (!string.IsNullOrEmpty(entry.RevitIds))
                {
                    var idLabel = new Label
                    {
                        Text = entry.RevitIds,
                        Font = new Font("Segoe UI", 8),
                        ForeColor = PurpleLight,
                        Left = 40,
                        Top = 46,
                        Width = cardWidth - 60,
                        Height = 16,
                        BackColor = Color.Transparent,
                    };
                    card.Controls.Add(idLabel);
                }

                if (!entry.Success && !string.IsNullOrEmpty(entry.ErrorMessage))
                {
                    var errorLabel = new Label
                    {
                        Text = "\u26A0 " + entry.ErrorMessage,
                        Font = new Font("Segoe UI", 8, FontStyle.Italic),
                        ForeColor = RedError,
                        Left = 40,
                        Top = 46 + (string.IsNullOrEmpty(entry.RevitIds) ? 0 : 16),
                        Width = cardWidth - 60,
                        Height = 16,
                        BackColor = Color.Transparent,
                    };
                    card.Controls.Add(errorLabel);
                }

                if (entry.StepResults != null)
                {
                    int stepTop = 62 + (string.IsNullOrEmpty(entry.RevitIds) && entry.Success ? 0 : 16);
                    if (!entry.Success && !string.IsNullOrEmpty(entry.ErrorMessage))
                        stepTop += 16;

                    foreach (var step in entry.StepResults)
                    {
                        var stepLabel = new Label
                        {
                            Text = "  \u2192 " + step,
                            Font = new Font("Segoe UI", 8),
                            ForeColor = TextMuted,
                            Left = 40,
                            Top = stepTop,
                            Width = cardWidth - 60,
                            Height = 18,
                            BackColor = Color.Transparent,
                        };
                        card.Controls.Add(stepLabel);
                        stepTop += 20;
                    }
                }

                _resultsPanel.Controls.Add(card);
            }
        }
    }
}
