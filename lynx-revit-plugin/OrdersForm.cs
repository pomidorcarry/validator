using System;
using System.Collections.Generic;
using System.Drawing;
using System.Net.Http;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    public class OrdersForm : Form
    {
        // ── Dark theme palette ──
        private static readonly Color DarkBg   = Color.FromArgb(11, 9, 20);
        private static readonly Color DarkPanel = Color.FromArgb(18, 16, 24);
        private static readonly Color DarkBorder = Color.FromArgb(42, 32, 48);
        private static readonly Color TextMain  = Color.FromArgb(224, 220, 232);
        private static readonly Color TextSec   = Color.FromArgb(136, 128, 160);
        private static readonly Color Accent    = Color.FromArgb(139, 92, 246);
        private static readonly Color Error     = Color.FromArgb(255, 107, 107);
        private static readonly Color Success   = Color.FromArgb(52, 211, 153);

        private readonly string _serverUrl;
        private readonly string _projectId;
        private FlowLayoutPanel _ordersPanel;
        private Button _refreshBtn;
        private Label _statusLabel;
        private List<ChangeOrder> _orders;

        public OrdersForm(string serverUrl, string projectId)
        {
            _serverUrl = serverUrl;
            _projectId = projectId;
            _orders = new List<ChangeOrder>();
            InitializeComponent();
            LoadOrders();
        }

        private static void StyleButton(Button btn, bool primary = false)
        {
            btn.FlatStyle = FlatStyle.Flat;
            btn.FlatAppearance.BorderColor = primary ? Accent : DarkBorder;
            btn.BackColor = primary ? Accent : DarkPanel;
            btn.ForeColor = primary ? Color.White : TextMain;
            btn.Font = new Font("Segoe UI", 9, FontStyle.Regular);
            btn.TextAlign = ContentAlignment.MiddleCenter;
        }

        private void InitializeComponent()
        {
            this.Text = "Приказы на изменения — Lynx";
            this.Width = 720;
            this.Height = 520;
            this.StartPosition = FormStartPosition.CenterParent;
            this.MinimumSize = new Size(500, 400);
            this.BackColor = DarkBg;
            this.ForeColor = TextMain;

            var header = new Label
            {
                Text = "Приказы на внесение изменений в модель",
                Font = new Font("Segoe UI", 13, FontStyle.Bold),
                Dock = DockStyle.Top,
                Padding = new Padding(14, 14, 14, 6),
                Height = 46,
                BackColor = DarkPanel,
                ForeColor = TextMain,
                TextAlign = ContentAlignment.MiddleLeft,
            };

            var headerLine = new Label
            {
                Dock = DockStyle.Top,
                Height = 1,
                BackColor = DarkBorder,
            };

            var topPanel = new Panel
            {
                Dock = DockStyle.Top,
                Height = 44,
                Padding = new Padding(12, 6, 12, 6),
                BackColor = DarkBg,
            };

            _statusLabel = new Label
            {
                Text = "Загрузка...",
                Left = 14,
                Top = 12,
                Width = 400,
                Height = 20,
                Font = new Font("Segoe UI", 9),
                ForeColor = TextSec,
                BackColor = Color.Transparent,
            };

            _refreshBtn = new Button
            {
                Text = "Обновить",
                Left = topPanel.Width - 110,
                Top = 9,
                Width = 96,
                Height = 26,
                Anchor = AnchorStyles.Right,
                Cursor = Cursors.Hand,
            };
            StyleButton(_refreshBtn);
            _refreshBtn.Click += (s, e) => LoadOrders();

            topPanel.Controls.Add(_statusLabel);
            topPanel.Controls.Add(_refreshBtn);

            _ordersPanel = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true,
                Padding = new Padding(14, 8, 14, 14),
                FlowDirection = FlowDirection.TopDown,
                WrapContents = false,
                BackColor = DarkBg,
            };

            this.Controls.Add(_ordersPanel);
            this.Controls.Add(topPanel);
            this.Controls.Add(headerLine);
            this.Controls.Add(header);
        }

        private void LoadOrders()
        {
            _statusLabel.Text = "Загрузка...";
            _refreshBtn.Enabled = false;

            try
            {
                using (var client = new HttpClient())
                {
                    client.Timeout = TimeSpan.FromSeconds(15);
                    var resp = client.GetAsync($"{_serverUrl}/api/v1/projects/{_projectId}/changes/for-revit")
                        .GetAwaiter().GetResult();

                    if (!resp.IsSuccessStatusCode)
                    {
                        _statusLabel.Text = "Ошибка загрузки (HTTP " + resp.StatusCode + ")";
                        _refreshBtn.Enabled = true;
                        return;
                    }

                    var json = resp.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    var data = Newtonsoft.Json.JsonConvert.DeserializeObject<Dictionary<string, object>>(json);
                    if (data == null || !data.ContainsKey("orders"))
                    {
                        _statusLabel.Text = "Нет данных";
                        _refreshBtn.Enabled = true;
                        return;
                    }

                    var ordersJson = Newtonsoft.Json.JsonConvert.SerializeObject(data["orders"]);
                    _orders = Newtonsoft.Json.JsonConvert.DeserializeObject<List<ChangeOrder>>(ordersJson);
                    RenderOrders();
                    _statusLabel.Text = $"Найдено приказов: {_orders.Count}";
                }
            }
            catch (Exception ex)
            {
                _statusLabel.Text = "Ошибка: " + ex.Message;
            }
            finally
            {
                _refreshBtn.Enabled = true;
            }
        }

        private void RenderOrders()
        {
            _ordersPanel.SuspendLayout();
            _ordersPanel.Controls.Clear();

            int cardWidth = this.ClientSize.Width - 48;

            if (_orders.Count == 0)
            {
                var empty = new Label
                {
                    Text = "Нет отправленных приказов.\nОтправьте приказ из веб-интерфейса Lynx.",
                    Width = cardWidth,
                    Height = 80,
                    Font = new Font("Segoe UI", 10),
                    ForeColor = TextSec,
                    BackColor = Color.Transparent,
                    TextAlign = ContentAlignment.MiddleCenter,
                    Padding = new Padding(20),
                };
                _ordersPanel.Controls.Add(empty);
                _ordersPanel.ResumeLayout();
                return;
            }

            foreach (var order in _orders)
            {
                int fixCount = order.Fixes?.Count ?? 0;
                int fixAreaH = Math.Min(fixCount * 38, 200);
                int cardH = 80 + fixAreaH;

                var card = new Panel
                {
                    Width = cardWidth,
                    Height = cardH,
                    Margin = new Padding(0, 0, 0, 10),
                    BackColor = DarkPanel,
                };

                // card border via paint
                card.Paint += (s, e) =>
                {
                    var c = s as Panel;
                    if (c == null) return;
                    using (var pen = new Pen(DarkBorder))
                    {
                        e.Graphics.DrawRectangle(pen, 0, 0, c.Width - 1, c.Height - 1);
                    }
                };

                // Status badge
                var approvedCount = order.Fixes?.FindAll(f => f.Status == "approved" || f.Status == "applied").Count ?? 0;
                var badgeColor = approvedCount > 0 ? Success : Accent;
                var badge = new Label
                {
                    Text = approvedCount > 0 ? $"{approvedCount}/{fixCount} ✓" : "sent",
                    Left = cardWidth - 80,
                    Top = 8,
                    Width = 66,
                    Height = 20,
                    Font = new Font("Segoe UI", 8, FontStyle.Bold),
                    ForeColor = badgeColor,
                    BackColor = Color.Transparent,
                    TextAlign = ContentAlignment.MiddleRight,
                };

                var titleLabel = new Label
                {
                    Text = order.Title ?? "(без названия)",
                    Left = 14,
                    Top = 8,
                    Width = cardWidth - 100,
                    Height = 22,
                    Font = new Font("Segoe UI", 11, FontStyle.Bold),
                    ForeColor = TextMain,
                    BackColor = Color.Transparent,
                };

                string dateStr = order.CreatedAt ?? "";
                if (dateStr.Length >= 16) dateStr = dateStr.Substring(0, 16).Replace("T", " ");

                var dateLabel = new Label
                {
                    Text = dateStr,
                    Left = 14,
                    Top = 30,
                    Width = cardWidth - 100,
                    Height = 16,
                    Font = new Font("Segoe UI", 8),
                    ForeColor = TextSec,
                    BackColor = Color.Transparent,
                };

                var fixesLabel = new Label
                {
                    Text = $"Исправлений: {fixCount}",
                    Left = 14,
                    Top = 50,
                    Width = cardWidth - 30,
                    Height = 16,
                    Font = new Font("Segoe UI", 8),
                    ForeColor = TextSec,
                    BackColor = Color.Transparent,
                };

                int boxTop = 70;
                int boxH = cardH - boxTop - 10;

                var fixesBox = new FlowLayoutPanel
                {
                    Left = 14,
                    Top = boxTop,
                    Width = cardWidth - 28,
                    Height = Math.Max(boxH, 26),
                    AutoScroll = true,
                    FlowDirection = FlowDirection.TopDown,
                    WrapContents = false,
                    BackColor = DarkBg,
                };

                if (order.Fixes != null)
                {
                    foreach (var fix in order.Fixes)
                    {
                        bool hasInstruction = !string.IsNullOrEmpty(fix.Instruction);
                        int fixH = hasInstruction ? 68 : 28;

                        var fixPanel = new Panel
                        {
                            Width = fixesBox.Width - 4,
                            Height = fixH,
                            Margin = new Padding(0, 0, 0, 3),
                            BackColor = Color.Transparent,
                        };

                        var statusColor = fix.Status == "approved" || fix.Status == "applied" ? Success :
                                          fix.Status == "rejected" ? Error : TextSec;

                        var revitIdStr = (fix.RevitElementIds != null && fix.RevitElementIds.Count > 0)
                            ? $" [Revit ID: {string.Join(", ", fix.RevitElementIds)}]"
                            : "";
                        var fixLabel = new Label
                        {
                            Text = $"[{fix.Status}] {fix.ElementName}{revitIdStr}: {fix.Message}",
                            Left = 6,
                            Top = 3,
                            Width = fixPanel.Width - 12,
                            Height = 22,
                            Font = new Font("Segoe UI", 8, FontStyle.Regular),
                            ForeColor = statusColor,
                            BackColor = Color.Transparent,
                        };

                        fixPanel.Controls.Add(fixLabel);

                        if (hasInstruction)
                        {
                            var instrLabel = new Label
                            {
                                Text = fix.Instruction,
                                Left = 6,
                                Top = 26,
                                Width = fixPanel.Width - 12,
                                Height = 38,
                                Font = new Font("Segoe UI", 7),
                                ForeColor = TextSec,
                                BackColor = Color.Transparent,
                            };
                            fixPanel.Controls.Add(instrLabel);
                        }

                        fixesBox.Controls.Add(fixPanel);
                    }
                }

                card.Controls.Add(badge);
                card.Controls.Add(titleLabel);
                card.Controls.Add(dateLabel);
                card.Controls.Add(fixesLabel);
                card.Controls.Add(fixesBox);

                _ordersPanel.Controls.Add(card);
            }

            _ordersPanel.ResumeLayout();
        }
    }

    public class ChangeFix
    {
        [Newtonsoft.Json.JsonProperty("fix_id")]
        public string FixId { get; set; }
        [Newtonsoft.Json.JsonProperty("element_name")]
        public string ElementName { get; set; }
        [Newtonsoft.Json.JsonProperty("element_global_id")]
        public string ElementGlobalId { get; set; }
        [Newtonsoft.Json.JsonProperty("element_ids")]
        public List<string> ElementIds { get; set; }
        [Newtonsoft.Json.JsonProperty("revit_element_ids")]
        public List<int> RevitElementIds { get; set; }
        [Newtonsoft.Json.JsonProperty("message")]
        public string Message { get; set; }
        [Newtonsoft.Json.JsonProperty("instruction")]
        public string Instruction { get; set; }
        [Newtonsoft.Json.JsonProperty("steps")]
        public List<FixStep> Steps { get; set; }
        [Newtonsoft.Json.JsonProperty("status")]
        public string Status { get; set; }
        [Newtonsoft.Json.JsonProperty("rule_key")]
        public string RuleKey { get; set; }
    }
    
    public class ChangeOrder
    {
        [Newtonsoft.Json.JsonProperty("id")]
        public string Id { get; set; }
        [Newtonsoft.Json.JsonProperty("title")]
        public string Title { get; set; }
        [Newtonsoft.Json.JsonProperty("created_at")]
        public string CreatedAt { get; set; }
        [Newtonsoft.Json.JsonProperty("fixes")]
        public List<ChangeFix> Fixes { get; set; }
    }
}
