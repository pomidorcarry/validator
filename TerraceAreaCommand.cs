using Autodesk.Revit.UI;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Architecture;
using System.Collections.Generic;
using System.Linq;

namespace RevitExtension
{
    [Transaction(TransactionMode.ReadOnly)]
    public class TerraceAreaCommand : IExternalCommand
    {
        public Result Execute(
            ExternalCommandData commandData,
            ref string message,
            ElementSet elements)
        {
            var uiDoc = commandData.Application.ActiveUIDocument;
            var doc = uiDoc.Document;

            var mainViews = GetMainFloorPlanViews(doc);

            if (mainViews.Count == 0)
            {
                TaskDialog.Show("Ошибка", "Не найдены виды планов этажей в основном файле.");
                return Result.Failed;
            }

            var selectForm = new ViewSelectionMultiForm(mainViews);
            if (selectForm.ShowDialog() != System.Windows.Forms.DialogResult.OK)
                return Result.Cancelled;

            var selectedViews = selectForm.GetSelectedViews();
            if (selectedViews.Count == 0)
            {
                TaskDialog.Show("Ошибка", "Выберите хотя бы один вид.");
                return Result.Failed;
            }

            var keywordsForm = new TerraceAreaForm();
            if (keywordsForm.ShowDialog() != System.Windows.Forms.DialogResult.OK)
                return Result.Cancelled;

            var keywords = keywordsForm.GetKeywords()
                .Select(k => k.ToLower().Trim())
                .Where(k => !string.IsNullOrEmpty(k))
                .ToList();

            if (keywords.Count == 0)
            {
                TaskDialog.Show("Ошибка", "Укажите хотя бы одно ключевое слово.");
                return Result.Failed;
            }

            var allRooms = new List<RoomDebugInfo>();
            var terraces = new List<TerraceInfo>();

            var linkCollector = new FilteredElementCollector(doc)
                .OfClass(typeof(RevitLinkInstance))
                .WhereElementIsNotElementType();

            var linkedDocs = new List<Document>();
            foreach (RevitLinkInstance link in linkCollector)
            {
                var linkedDoc = link.GetLinkDocument();
                if (linkedDoc != null)
                {
                    linkedDocs.Add(linkedDoc);
                }
            }

            if (linkedDocs.Count == 0)
            {
                TaskDialog.Show("Ошибка", "В модели не найдены связанные файлы.");
                return Result.Failed;
            }

            foreach (var selectedView in selectedViews)
            {
                var viewPlan = doc.GetElement(selectedView.ViewId) as ViewPlan;
                var levelName = viewPlan?.GenLevel?.Name ?? "Неизвестно";

                foreach (var linkedDoc in linkedDocs)
                {
                    var docTitle = linkedDoc.Title;

                    var roomCollector = new FilteredElementCollector(linkedDoc)
                        .OfCategory(BuiltInCategory.OST_Rooms)
                        .WhereElementIsNotElementType();

                    foreach (Room room in roomCollector)
                    {
                        var roomLevelName = room.Level?.Name ?? "";
                        if (roomLevelName != levelName)
                            continue;

                        var roomName = room.Name ?? "";
                        var roomNameLower = roomName.ToLower();
                        var areaM2 = room.Area * 0.092903;

                        allRooms.Add(new RoomDebugInfo
                        {
                            ViewName = selectedView.Name,
                            LevelName = levelName,
                            RoomName = roomName,
                            AreaM2 = areaM2,
                            LinkInfo = docTitle,
                            IsTerrace = keywords.Any(k => roomNameLower.Contains(k))
                        });

                        if (keywords.Any(k => roomNameLower.Contains(k)))
                        {
                            terraces.Add(new TerraceInfo
                            {
                                Name = roomName,
                                AreaM2 = areaM2,
                                Level = levelName,
                                View = selectedView.Name,
                                LinkInfo = docTitle
                            });
                        }
                    }
                }
            }

            var debugForm = new DebugRoomsForm(allRooms, keywords);
            debugForm.ShowDialog();

            if (terraces.Count == 0)
            {
                TaskDialog.Show("Результат", 
                    "Террасы не найдены.\n\n" +
                    "Проверьте названия в окне отладки.");
                return Result.Succeeded;
            }

            var resultsForm = new TerraceResultsForm(terraces);
            resultsForm.ShowDialog();

            return Result.Succeeded;
        }

        private List<ViewSelectItem> GetMainFloorPlanViews(Document doc)
        {
            var views = new List<ViewSelectItem>();

            var collector = new FilteredElementCollector(doc)
                .OfClass(typeof(ViewPlan))
                .WhereElementIsNotElementType();

            foreach (ViewPlan view in collector)
            {
                if (view.ViewType == ViewType.FloorPlan || 
                    view.ViewType == ViewType.AreaPlan)
                {
                    var levelName = view.GenLevel?.Name ?? "Неизвестно";

                    views.Add(new ViewSelectItem
                    {
                        ViewId = view.Id,
                        Name = $"{view.Name} ({levelName})"
                    });
                }
            }

            return views.OrderBy(v => v.Name).ToList();
        }
    }

    public class ViewSelectItem
    {
        public ElementId ViewId { get; set; }
        public string Name { get; set; }
    }

    public class RoomDebugInfo
    {
        public string ViewName { get; set; }
        public string LevelName { get; set; }
        public string RoomName { get; set; }
        public double AreaM2 { get; set; }
        public string LinkInfo { get; set; }
        public bool IsTerrace { get; set; }
    }

    public class TerraceInfo
    {
        public string Name { get; set; }
        public double AreaM2 { get; set; }
        public string Level { get; set; }
        public string View { get; set; }
        public string LinkInfo { get; set; }
    }

    public class ViewSelectionMultiForm : System.Windows.Forms.Form
    {
        private System.Windows.Forms.CheckedListBox checkedListBox;
        private System.Windows.Forms.Button selectAllButton;
        private System.Windows.Forms.Button deselectAllButton;
        private System.Windows.Forms.Button okButton;
        private System.Windows.Forms.Button cancelButton;
        private List<ViewSelectItem> _views;

        public ViewSelectionMultiForm(List<ViewSelectItem> views)
        {
            _views = views;
            InitializeComponent();
            LoadViews();
        }

        private void InitializeComponent()
        {
            this.Text = "Выбор видов плана этажа";
            this.Size = new System.Drawing.Size(450, 500);
            this.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedDialog;
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.MaximizeBox = false;
            this.MinimizeBox = false;

            var label = new System.Windows.Forms.Label
            {
                Text = "Выберите виды планов этажа:\n(помещения будут взяты из связанного файла AR)",
                Location = new System.Drawing.Point(15, 15),
                AutoSize = false,
                Size = new System.Drawing.Size(400, 40)
            };
            this.Controls.Add(label);

            checkedListBox = new System.Windows.Forms.CheckedListBox
            {
                Location = new System.Drawing.Point(15, 60),
                Size = new System.Drawing.Size(400, 350),
                CheckOnClick = true,
                ScrollAlwaysVisible = true
            };
            this.Controls.Add(checkedListBox);

            selectAllButton = new System.Windows.Forms.Button
            {
                Text = "Выбрать все",
                Location = new System.Drawing.Point(15, 420),
                Size = new System.Drawing.Size(100, 30)
            };
            selectAllButton.Click += SelectAllButton_Click;
            this.Controls.Add(selectAllButton);

            deselectAllButton = new System.Windows.Forms.Button
            {
                Text = "Снять выбор",
                Location = new System.Drawing.Point(125, 420),
                Size = new System.Drawing.Size(100, 30)
            };
            deselectAllButton.Click += DeselectAllButton_Click;
            this.Controls.Add(deselectAllButton);

            okButton = new System.Windows.Forms.Button
            {
                Text = "Далее",
                Location = new System.Drawing.Point(235, 420),
                Size = new System.Drawing.Size(90, 30),
                DialogResult = System.Windows.Forms.DialogResult.OK
            };
            this.Controls.Add(okButton);

            cancelButton = new System.Windows.Forms.Button
            {
                Text = "Отмена",
                Location = new System.Drawing.Point(335, 420),
                Size = new System.Drawing.Size(80, 30),
                DialogResult = System.Windows.Forms.DialogResult.Cancel
            };
            this.Controls.Add(cancelButton);

            this.AcceptButton = okButton;
            this.CancelButton = cancelButton;
        }

        private void LoadViews()
        {
            foreach (var view in _views)
            {
                checkedListBox.Items.Add(view.Name, true);
            }
        }

        private void SelectAllButton_Click(object sender, System.EventArgs e)
        {
            for (int i = 0; i < checkedListBox.Items.Count; i++)
            {
                checkedListBox.SetItemChecked(i, true);
            }
        }

        private void DeselectAllButton_Click(object sender, System.EventArgs e)
        {
            for (int i = 0; i < checkedListBox.Items.Count; i++)
            {
                checkedListBox.SetItemChecked(i, false);
            }
        }

        public List<ViewSelectItem> GetSelectedViews()
        {
            var selected = new List<ViewSelectItem>();
            for (int i = 0; i < checkedListBox.Items.Count; i++)
            {
                if (checkedListBox.GetItemChecked(i))
                {
                    selected.Add(_views[i]);
                }
            }
            return selected;
        }
    }
}
