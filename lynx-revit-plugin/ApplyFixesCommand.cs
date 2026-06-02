using Autodesk.Revit.UI;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace LynxRevitPlugin
{
    [Transaction(TransactionMode.Manual)]
    public class ApplyFixesCommand : IExternalCommand
    {
        private static bool _isApplying;

        public Result Execute(
            ExternalCommandData commandData,
            ref string message,
            ElementSet elements)
        {
            if (_isApplying)
            {
                TaskDialog.Show("Lynx", "Применение уже выполняется. Дождитесь завершения.");
                return Result.Failed;
            }

            var settings = SettingsForm.LoadSettingsData();
            if (string.IsNullOrEmpty(settings.ServerUrl))
            {
                TaskDialog.Show("Lynx", "Настройте URL сервера в настройках плагина.");
                return Result.Failed;
            }

            if (string.IsNullOrEmpty(settings.ProjectId) || settings.ProjectId == "default")
            {
                TaskDialog.Show("Lynx", "Укажите Project ID в настройках плагина.");
                return Result.Failed;
            }

            UIDocument uidoc = commandData.Application.ActiveUIDocument;
            Document doc = uidoc.Document;

            try
            {
                _isApplying = true;

                // Fetch approved fixes from server
                var fixes = FetchApprovedFixes(settings.ServerUrl, settings.ProjectId);
                if (fixes == null || fixes.Count == 0)
                {
                    TaskDialog.Show("Lynx", "Нет утверждённых исправлений для применения.");
                    return Result.Failed;
                }

                // Show review dialog
                using (var form = new FixReviewForm(fixes))
                {
                    if (form.ShowDialog() != DialogResult.OK)
                        return Result.Cancelled;
                }

                // Apply selected fixes
                int applied = 0;
                int failed = 0;
                var results = new List<string>();

                foreach (var fix in fixes)
                {
                    if (fix.UserAction == FixAction.Skip)
                        continue;

                    try
                    {
                        Element elem = FindElement(doc, fix.ElementGlobalId, fix.IfcGuidHint);
                        if (elem == null)
                        {
                            results.Add($"✗ {fix.ElementName}: элемент не найден");
                            failed++;
                            ReportFixResult(settings.ServerUrl, settings.ProjectId, fix.FixId, false, "Element not found");
                            continue;
                        }

                        using (Transaction tx = new Transaction(doc, fix.Description))
                        {
                            tx.Start();
                            bool stepOk = true;

                            foreach (var step in fix.Steps)
                            {
                                if (step.Action == "set_param")
                                {
                                    Parameter param = elem.LookupParameter(step.Param);
                                    if (param != null)
                                    {
                                        if (step.ValueType == "number" && double.TryParse(step.Value, out double numVal))
                                            param.Set(numVal);
                                        else if (step.ValueType == "integer" && int.TryParse(step.Value, out int intVal))
                                            param.Set(intVal);
                                        else
                                            param.Set(step.Value);
                                    }
                                    else
                                    {
                                        stepOk = false;
                                        results.Add($"  ⚠ Параметр {step.Param} не найден у элемента");
                                    }
                                }
                                else if (step.Action == "copy_param")
                                {
                                    Parameter from = elem.LookupParameter(step.FromParam);
                                    Parameter to = elem.LookupParameter(step.ToParam);
                                    if (from != null && to != null)
                                    {
                                        string val = from.AsString();
                                        if (!string.IsNullOrEmpty(val))
                                            to.Set(val);
                                    }
                                    else
                                    {
                                        stepOk = false;
                                    }
                                }
                                else if (step.Action == "set_system")
                                {
                                    // Set system via parameter
                                    Parameter sysParam = elem.LookupParameter("BRU_Система");
                                    if (sysParam != null)
                                        sysParam.Set(step.SystemName);
                                }
                            }

                            if (stepOk)
                            {
                                tx.Commit();
                                applied++;
                                results.Add($"✓ {fix.ElementName}: {fix.Description}");
                                ReportFixResult(settings.ServerUrl, settings.ProjectId, fix.FixId, true, null);
                            }
                            else
                            {
                                tx.RollBack();
                                failed++;
                                results.Add($"✗ {fix.ElementName}: ошибка применения шагов");
                                ReportFixResult(settings.ServerUrl, settings.ProjectId, fix.FixId, false, "Step application failed");
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        failed++;
                        results.Add($"✗ {fix.ElementName}: {ex.Message}");
                        ReportFixResult(settings.ServerUrl, settings.ProjectId, fix.FixId, false, ex.Message);
                    }
                }

                // Show summary
                var summary = $"Применено: {applied}\nОшибок: {failed}\n\nДетали:\n" + string.Join("\n", results);
                TaskDialog.Show("Lynx — Результат исправлений", summary);

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                TaskDialog.Show("Lynx", $"Ошибка: {ex.Message}");
                message = ex.Message;
                return Result.Failed;
            }
            finally
            {
                _isApplying = false;
            }
        }

        private Element FindElement(Document doc, string globalId, string ifcGuidHint)
        {
            // Strategy 1: Try to find by IfcGUID parameter
            if (!string.IsNullOrEmpty(ifcGuidHint))
            {
                var collector = new FilteredElementCollector(doc)
                    .WhereElementIsNotElementType();

                var paramProv = new ParameterValueProvider(new ElementId(BuiltInParameter.IFC_GUID));
                var valRule = new FilterStringEquals();
                var rule = new FilterStringRule(paramProv, valRule, ifcGuidHint, false);
                var filter = new ElementParameterFilter(rule);

                var found = collector.WherePasses(filter).FirstElement();
                if (found != null) return found;
            }

            // Strategy 2: Try by Element.UniqueId
            if (!string.IsNullOrEmpty(globalId))
            {
                try
                {
                    Element elem = doc.GetElement(globalId);
                    if (elem != null) return elem;
                }
                catch { }

                // Strategy 3: Try by ADSK_ГлобальныйИдентификатор parameter
                var collector2 = new FilteredElementCollector(doc)
                    .WhereElementIsNotElementType();

                var paramProv2 = new ParameterValueProvider(new ElementId(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS));
                // Try different parameter names for global ID
                var paramFilter = new ElementCategoryFilter(BuiltInCategory.OST_PipeCurves);
                // Broader search — iterate through elements
                var allElements = new FilteredElementCollector(doc)
                    .WhereElementIsNotElementType()
                    .ToElements();

                foreach (Element el in allElements)
                {
                    foreach (Parameter p in el.Parameters)
                    {
                        string pname = p.Definition?.Name ?? "";
                        if (pname.Contains("Глобальный") || pname.Contains("Global") || pname == "IfcGUID")
                        {
                            string val = p.AsString();
                            if (!string.IsNullOrEmpty(val) && val.Contains(globalId))
                                return el;
                        }
                    }
                }
            }

            return null;
        }

        private List<FixInstruction> FetchApprovedFixes(string serverUrl, string projectId)
        {
            try
            {
                using (var client = new HttpClient())
                {
                    client.Timeout = TimeSpan.FromSeconds(30);
                    var resp = client.GetAsync($"{serverUrl}/api/v1/projects/{projectId}/fix-suggestions?status=approved")
                        .GetAwaiter().GetResult();

                    if (!resp.IsSuccessStatusCode)
                        return null;

                    var json = resp.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    var data = Newtonsoft.Json.JsonConvert.DeserializeObject<Dictionary<string, object>>(json);
                    if (data == null) return null;

                    var fixesJson = Newtonsoft.Json.JsonConvert.SerializeObject(data["fixes"]);
                    var fixes = Newtonsoft.Json.JsonConvert.DeserializeObject<List<FixInstruction>>(fixesJson);
                    return fixes;
                }
            }
            catch
            {
                return null;
            }
        }

        private void ReportFixResult(string serverUrl, string projectId, string fixId, bool success, string errorMessage)
        {
            try
            {
                using (var client = new HttpClient())
                {
                    client.Timeout = TimeSpan.FromSeconds(10);
                    var content = new FormUrlEncodedContent(new[]
                    {
                        new KeyValuePair<string, string>("success", success.ToString().ToLower()),
                        new KeyValuePair<string, string>("error_message", errorMessage ?? ""),
                    });
                    client.PostAsync(
                        $"{serverUrl}/api/v1/projects/{projectId}/fix-suggestions/{fixId}/result",
                        content).GetAwaiter().GetResult();
                }
            }
            catch { }
        }
    }

    public class FixInstruction
    {
        public string FixId { get; set; }
        public int IssueIndex { get; set; }
        public string ElementGlobalId { get; set; }
        public string ElementName { get; set; }
        public string Description { get; set; }
        public string Risk { get; set; }
        public string IfcGuidHint { get; set; }
        public string Status { get; set; }
        public string IssueMessage { get; set; }
        public List<FixStep> Steps { get; set; }
        public FixAction UserAction { get; set; } = FixAction.Apply;
    }

    public class FixStep
    {
        public string Action { get; set; }
        public string Param { get; set; }
        public string Value { get; set; }
        public string ValueType { get; set; }
        public string FromParam { get; set; }
        public string ToParam { get; set; }
        public string SystemName { get; set; }
    }

    public enum FixAction
    {
        Apply,
        Skip
    }
}
