using Autodesk.Revit.UI;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using System;
using System.IO;
using System.Net.Http;
using System.Threading.Tasks;

namespace LynxRevitPlugin
{
    [Transaction(TransactionMode.Manual)]
    public class ExportIfcCommand : IExternalCommand
    {
        private static bool _isUploading;

        public Result Execute(
            ExternalCommandData commandData,
            ref string message,
            ElementSet elements)
        {
            UIDocument uidoc = commandData.Application.ActiveUIDocument;
            Document doc = uidoc.Document;

            if (_isUploading)
            {
                TaskDialog.Show("Lynx", "Выгрузка уже выполняется. Дождитесь завершения.");
                return Result.Failed;
            }

            var settings = SettingsForm.LoadSettingsData();

            if (string.IsNullOrEmpty(settings.ServerUrl))
            {
                TaskDialog.Show("Lynx", "Настройте URL сервера в настройках плагина.");
                return Result.Failed;
            }

            if (string.IsNullOrEmpty(doc.PathName))
            {
                TaskDialog.Show("Lynx", "Сохраните документ перед экспортом.");
                return Result.Failed;
            }

            try
            {
                TaskDialog.Show("Lynx", "Экспорт IFC начат.\nЭто окно можно закрыть.");

                string exportFolder = GetExportFolder();
                string ifcFileName = $"{doc.Title}_{DateTime.Now:yyyyMMdd_HHmmss}.ifc";
                string ifcPath = Path.Combine(exportFolder, ifcFileName);

                ExportIfc(doc, exportFolder, ifcFileName);

                _isUploading = true;

                Task.Run(async () =>
                {
                    try
                    {
                        var result = await UploadIfcToServerAsync(ifcPath, settings, doc);
                        var evt = new ShowUploadResultEvent();
                        if (result.Success)
                        {
                            evt.Message =
                                $"Модель отправлена.\n\n" +
                                $"Model ID: {result.ModelVersionId}\n" +
                                $"Status: {result.Status}";
                        }
                        else
                        {
                            evt.Message = $"Ошибка: {result.ErrorMessage}";
                        }
                        ExternalEvent.Create(evt).Raise();
                    }
                    finally
                    {
                        _isUploading = false;
                    }
                });

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                _isUploading = false;
                TaskDialog.Show("Lynx", $"Ошибка: {ex.Message}");
                message = ex.Message;
                return Result.Failed;
            }
        }

        private string GetExportFolder()
        {
            string appDataPath = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            string lynxFolder = Path.Combine(appDataPath, "Lynx", "IFC");
            
            if (!Directory.Exists(lynxFolder))
            {
                Directory.CreateDirectory(lynxFolder);
            }
            
            return lynxFolder;
        }

        private void ExportIfc(Document doc, string folder, string fileName)
        {
            if (!Directory.Exists(folder))
            {
                Directory.CreateDirectory(folder);
            }

            IFCExportOptions options = new IFCExportOptions
            {
                FileVersion = IFCVersion.IFC4,
                ExportBaseQuantities = true
            };

            bool exportResult = doc.Export(folder, fileName, options);

            if (!exportResult)
            {
                throw new Exception("IFC export failed. Check document state.");
            }
        }

        private async Task<UploadResult> UploadIfcToServerAsync(string ifcPath, SettingsData settings, Document doc)
        {
            using (var client = new HttpClient())
            {
                client.Timeout = TimeSpan.FromMinutes(10);

                using (var form = new MultipartFormDataContent())
                {
                    form.Add(new StringContent(settings.ProjectId), "project_id");
                    form.Add(new StringContent(doc.Title), "model_name");
                    form.Add(new StringContent(settings.RulesetId), "ruleset_id");
                    form.Add(new StringContent("VIV"), "discipline");
                    form.Add(new StringContent(doc.Application.VersionNumber), "revit_version");
                    form.Add(new StringContent("0.1.0"), "plugin_version");
                    form.Add(new StringContent(doc.PathName ?? ""), "source_file_name");

                    var fileStream = File.OpenRead(ifcPath);
                    using (var fileContent = new StreamContent(fileStream))
                    {
                        fileContent.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream");
                        form.Add(fileContent, "file", Path.GetFileName(ifcPath));

                        var response = await client.PostAsync($"{settings.ServerUrl}/api/v1/models/upload", form);

                        if (response.IsSuccessStatusCode)
                        {
                            var json = await response.Content.ReadAsStringAsync();
                            var data = Newtonsoft.Json.JsonConvert.DeserializeObject<System.Collections.Generic.Dictionary<string, object>>(json);
                            return new UploadResult
                            {
                                Success = true,
                                ModelVersionId = data["model_version_id"]?.ToString(),
                                Status = data["status"]?.ToString()
                            };
                        }
                        else
                        {
                            var error = await response.Content.ReadAsStringAsync();
                            return new UploadResult
                            {
                                Success = false,
                                ErrorMessage = $"Server error: {response.StatusCode} - {error}"
                            };
                        }
                    }
                }
            }
        }
    }

    public class UploadResult
    {
        public bool Success { get; set; }
        public string ModelVersionId { get; set; }
        public string Status { get; set; }
        public string ErrorMessage { get; set; }
    }

    public class ShowUploadResultEvent : IExternalEventHandler
    {
        public string Message { get; set; }

        public void Execute(UIApplication app)
        {
            TaskDialog.Show("Lynx", Message);
        }

        public string GetName() => "Lynx Upload Result";
    }
}