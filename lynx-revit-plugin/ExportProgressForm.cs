using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    public class ExportProgressForm : Form
    {
        private Label titleLabel;
        private Label subtitleLabel;
        private Label statusLabel;
        private Label progressLabel;
        private Panel progressTrack;
        private Panel progressFill;
        private Button closeButton;
        private Timer autoCloseTimer;
        private bool _completed;
        private int _progress;

        private static readonly Color DarkBg = Color.FromArgb(11, 11, 28);
        private static readonly Color DarkSurface = Color.FromArgb(22, 22, 48);
        private static readonly Color PurplePrimary = Color.FromArgb(108, 99, 255);
        private static readonly Color PurpleLight = Color.FromArgb(179, 136, 255);
        private static readonly Color TextPrimary = Color.FromArgb(235, 235, 245);
        private static readonly Color TextMuted = Color.FromArgb(150, 150, 175);
        private static readonly Color GreenOk = Color.FromArgb(76, 175, 80);
        private static readonly Color RedError = Color.FromArgb(244, 67, 54);

        public ExportProgressForm()
        {
            InitializeComponent();
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint | ControlStyles.DoubleBuffer | ControlStyles.ResizeRedraw, true);
        }

        private void InitializeComponent()
        {
            Width = 460;
            Height = 260;
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.CenterScreen;
            ShowInTaskbar = true;
            Text = "Lynx";

            titleLabel = new Label
            {
                Text = "Lynx",
                Font = new Font("Segoe UI", 22, FontStyle.Bold),
                ForeColor = PurpleLight,
                BackColor = DarkBg,
                Left = 24,
                Top = 18,
                Width = 100,
                Height = 36
            };

            subtitleLabel = new Label
            {
                Text = "Выгрузка модели",
                Font = new Font("Segoe UI", 10),
                ForeColor = TextMuted,
                BackColor = DarkBg,
                Left = 24,
                Top = 54,
                Width = 200,
                Height = 18
            };

            statusLabel = new Label
            {
                Text = "Экспорт IFC...",
                Font = new Font("Segoe UI", 11, FontStyle.Bold),
                ForeColor = TextPrimary,
                BackColor = DarkBg,
                Left = 24,
                Top = 100,
                Width = 420,
                Height = 22
            };

            progressTrack = new Panel
            {
                Left = 24,
                Top = 138,
                Width = 360,
                Height = 10,
                BackColor = Color.FromArgb(35, 35, 65)
            };

            progressFill = new Panel
            {
                Left = 24,
                Top = 138,
                Width = 0,
                Height = 10,
                BackColor = PurplePrimary
            };

            progressLabel = new Label
            {
                Text = "0%",
                Font = new Font("Segoe UI", 9, FontStyle.Bold),
                ForeColor = PurpleLight,
                BackColor = DarkBg,
                Left = 394,
                Top = 136,
                Width = 46,
                Height = 16,
                TextAlign = ContentAlignment.MiddleRight
            };

            closeButton = new Button
            {
                Text = "OK",
                Font = new Font("Segoe UI", 9, FontStyle.Bold),
                ForeColor = Color.White,
                BackColor = PurplePrimary,
                FlatStyle = FlatStyle.Flat,
                Left = 356,
                Top = 200,
                Width = 80,
                Height = 30,
                Visible = false,
                Cursor = Cursors.Hand
            };
            closeButton.FlatAppearance.BorderSize = 0;
            closeButton.Click += (s, e) => Close();

            Controls.AddRange(new Control[] {
                titleLabel, subtitleLabel, statusLabel,
                progressTrack, progressFill, progressLabel,
                closeButton
            });

            progressFill.BringToFront();
            progressLabel.BringToFront();
        }

        protected override void OnPaintBackground(PaintEventArgs e)
        {
            var rect = ClientRectangle;
            using (var brush = new LinearGradientBrush(rect, DarkBg, DarkSurface, LinearGradientMode.Vertical))
            {
                e.Graphics.FillRectangle(brush, rect);
            }
            using (var pen = new Pen(PurplePrimary, 3))
            {
                e.Graphics.DrawLine(pen, 0, 0, Width, 0);
            }
            using (var pen = new Pen(Color.FromArgb(40, 40, 80), 1))
            {
                e.Graphics.DrawRectangle(pen, 0, 0, Width - 1, Height - 1);
            }
        }

        public void SetStatus(string text)
        {
            if (InvokeRequired) { Invoke(new Action(() => SetStatus(text))); return; }
            statusLabel.Text = text;
        }

        public void SetProgress(int percent)
        {
            if (InvokeRequired) { Invoke(new Action(() => SetProgress(percent))); return; }
            _progress = Math.Max(0, Math.Min(100, percent));
            progressFill.Width = (int)(progressTrack.Width * _progress / 100.0);
            progressLabel.Text = $"{_progress}%";
            progressFill.Invalidate();
        }

        public void SetCompleted(bool success, string message)
        {
            if (InvokeRequired) { Invoke(new Action(() => SetCompleted(success, message))); return; }
            if (_completed) return;
            _completed = true;

            progressFill.BackColor = success ? GreenOk : RedError;
            progressFill.Width = progressTrack.Width;
            progressLabel.Text = success ? "Готово" : "Ошибка";
            progressLabel.ForeColor = success ? GreenOk : RedError;
            statusLabel.Text = message;

            closeButton.Visible = true;
            closeButton.Focus();

            autoCloseTimer = new Timer { Interval = 4000 };
            autoCloseTimer.Tick += (s, e) => { autoCloseTimer.Stop(); Close(); };
            autoCloseTimer.Start();
        }

        public bool IsCompleted => _completed;
    }
}
