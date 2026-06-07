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
                var reportEntries = new List<FixReportEntry>();

                foreach (var fix in fixes)
                {
                    if (fix.UserAction == FixAction.Skip)
                        continue;

                    var revitIdStr = (fix.RevitElementIds != null && fix.RevitElementIds.Count > 0)
                        ? $"Revit ID: {string.Join(", ", fix.RevitElementIds)}" : "";

                    try
                    {
                        Element elem = FindElement(doc, fix.ElementGlobalId, fix.IfcGuidHint, fix.ElementIds, fix.RevitElementIds);
                        if (elem == null)
                        {
                            failed++;
                            reportEntries.Add(new FixReportEntry
                            {
                                ElementName = fix.ElementName,
                                Description = fix.Description,
                                Success = false,
                                RevitIds = revitIdStr,
                                ErrorMessage = "Элемент не найден в документе",
                            });
                            ReportFixResult(settings.ServerUrl, settings.ProjectId, fix.FixId, false, "Element not found");
                            continue;
                        }

                        var stepResults = new List<string>();

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
                                        stepResults.Add($"Установлен параметр {step.Param} = {step.Value}");
                                    }
                                    else
                                    {
                                        stepOk = false;
                                        stepResults.Add($"Параметр {step.Param} не найден");
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
                                        stepResults.Add($"Скопирован {step.FromParam} в {step.ToParam}");
                                    }
                                    else
                                    {
                                        stepOk = false;
                                        stepResults.Add($"Копирование {step.FromParam} -> {step.ToParam} не удалось");
                                    }
                                }
                                else if (step.Action == "set_system")
                                {
                                    Parameter sysParam = elem.LookupParameter("BRU_Система");
                                    if (sysParam != null)
                                    {
                                        sysParam.Set(step.SystemName);
                                        stepResults.Add($"Установлена система: {step.SystemName}");
                                    }
                                }
                            }

                            if (stepOk)
                            {
                                tx.Commit();
                                applied++;
                                reportEntries.Add(new FixReportEntry
                                {
                                    ElementName = fix.ElementName,
                                    Description = fix.Description,
                                    Success = true,
                                    RevitIds = revitIdStr,
                                    StepResults = stepResults,
                                });
                                ReportFixResult(settings.ServerUrl, settings.ProjectId, fix.FixId, true, null);
                            }
                            else
                            {
                                tx.RollBack();
                                failed++;
                                reportEntries.Add(new FixReportEntry
                                {
                                    ElementName = fix.ElementName,
                                    Description = fix.Description,
                                    Success = false,
                                    RevitIds = revitIdStr,
                                    ErrorMessage = "Ошибка применения одного или нескольких шагов",
                                    StepResults = stepResults,
                                });
                                ReportFixResult(settings.ServerUrl, settings.ProjectId, fix.FixId, false, "Step application failed");
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        failed++;
                        reportEntries.Add(new FixReportEntry
                        {
                            ElementName = fix.ElementName,
                            Description = fix.Description,
                            Success = false,
                            RevitIds = revitIdStr,
                            ErrorMessage = ex.Message,
                        });
                        ReportFixResult(settings.ServerUrl, settings.ProjectId, fix.FixId, false, ex.Message);
                    }
                }

                // Show detailed report
                using (var form = new FixResultForm(applied, failed, reportEntries))
                {
                    form.ShowDialog();
                }

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

        private Element FindElement(Document doc, string globalId, string ifcGuidHint, List<string> elementIds = null, List<int> revitElementIds = null)
        {
            // Strategy 0: Direct Revit ElementId lookup (fastest)
            if (revitElementIds != null)
            {
#pragma warning disable CS0618
                foreach (int rid in revitElementIds)
                {
                    try
                    {
                        Element el = doc.GetElement(new ElementId(rid));
                        if (el != null) return el;
                    }
                    catch { }
                }
#pragma warning restore CS0618
            }

            // Collect all string IDs to try
            var idsToTry = new List<string>();
            if (!string.IsNullOrEmpty(ifcGuidHint)) idsToTry.Add(ifcGuidHint);
            if (!string.IsNullOrEmpty(globalId)) idsToTry.Add(globalId);
            if (elementIds != null) idsToTry.AddRange(elementIds);
            idsToTry = idsToTry.Distinct().ToList();

            // Strategy 1: Try IfcGUID parameter match for each ID
            foreach (var id in idsToTry)
            {
                var collector = new FilteredElementCollector(doc)
                    .WhereElementIsNotElementType();
                var paramProv = new ParameterValueProvider(new ElementId(BuiltInParameter.IFC_GUID));
                var valRule = new FilterStringEquals();
                var rule = new FilterStringRule(paramProv, valRule, id);
                var filter = new ElementParameterFilter(rule);
                var found = collector.WherePasses(filter).FirstElement();
                if (found != null) return found;
            }

            // Strategy 2: Try by Element.UniqueId for each ID
            foreach (var id in idsToTry)
            {
                try
                {
                    Element elem = doc.GetElement(id);
                    if (elem != null) return elem;
                }
                catch { }
            }

            // Strategy 3: Broader search — iterate all elements, match by parameter
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
                        if (!string.IsNullOrEmpty(val))
                        {
                            foreach (var id in idsToTry)
                            {
                                if (val.Contains(id))
                                    return el;
                            }
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
                    // Fetch sent orders from the changes API
                    var resp = client.GetAsync($"{serverUrl}/api/v1/projects/{projectId}/changes/for-revit")
                        .GetAwaiter().GetResult();

                    if (!resp.IsSuccessStatusCode)
                        return null;

                    var json = resp.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    var data = Newtonsoft.Json.JsonConvert.DeserializeObject<Dictionary<string, object>>(json);
                    if (data == null || !data.ContainsKey("orders"))
                        return null;

                    var ordersJson = Newtonsoft.Json.JsonConvert.SerializeObject(data["orders"]);
                    var orders = Newtonsoft.Json.JsonConvert.DeserializeObject<List<ChangeOrder>>(ordersJson);

                    var fixes = new List<FixInstruction>();
                    foreach (var order in orders)
                    {
                        if (order.Fixes == null) continue;
                        foreach (var cf in order.Fixes)
                        {
                            if (cf.Status == "rejected") continue;
                            var eid = cf.ElementGlobalId ?? "";
                            var eids = cf.ElementIds ?? new List<string>();
                            if (string.IsNullOrEmpty(eid) && eids.Count > 0)
                                eid = eids[0];
                            var revitIds = cf.RevitElementIds ?? new List<int>();
                            if (revitIds.Count == 0)
                            {
                                // Fallback: try to parse from element_ids -> they might be numeric
                                foreach (var id in eids)
                                {
                                    if (int.TryParse(id, out int parsed))
                                    {
                                        revitIds.Add(parsed);
                                    }
                                }
                            }
                            fixes.Add(new FixInstruction
                            {
                                FixId = cf.FixId ?? Guid.NewGuid().ToString(),
                                OrderId = order.Id,
                                ElementName = cf.ElementName ?? "",
                                ElementGlobalId = eid,
                                ElementIds = eids,
                                RevitElementIds = revitIds,
                                Description = cf.Message ?? cf.Instruction ?? "Приказ: " + (order.Title ?? ""),
                                Risk = "medium",
                                IssueMessage = cf.Message ?? "",
                                Steps = cf.Steps ?? new List<FixStep>(),
                            });
                        }
                    }

                    return fixes.Count > 0 ? fixes : null;
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("FetchApprovedFixes error: " + ex.Message);
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
                        $"{serverUrl}/api/v1/projects/{projectId}/changes/{fixId}/mark-applied",
                        content).GetAwaiter().GetResult();
                }
            }
            catch { }
        }
    }

    public class FixInstruction
    {
        public string FixId { get; set; }
        public string OrderId { get; set; }
        public string ElementName { get; set; }
        public string ElementGlobalId { get; set; }
        public List<string> ElementIds { get; set; }
        public List<int> RevitElementIds { get; set; }
        public string Description { get; set; }
        public string Risk { get; set; }
        public string IssueMessage { get; set; }
        public string IfcGuidHint { get; set; }
        public List<FixStep> Steps { get; set; }
        public FixAction UserAction { get; set; }
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
