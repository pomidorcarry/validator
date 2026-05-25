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

            ProgressFormHandle formHandle = null;

            try
            {
                formHandle = new ProgressFormHandle();
                formHandle.Show();

                string exportFolder = GetExportFolder();
                string ifcFileName = $"{doc.Title}_{DateTime.Now:yyyyMMdd_HHmmss}.ifc";
                string ifcPath = Path.Combine(exportFolder, ifcFileName);

                formHandle.SetStatus("Экспорт IFC...");
                formHandle.SetProgress(5);

                using (Transaction t = new Transaction(doc, "IFC Export"))
                {
                    t.Start();
                    ExportIfc(doc, exportFolder, ifcFileName);
                    t.Commit();
                }

                formHandle.SetStatus("Экспорт завершён");
                formHandle.SetProgress(50);

                var docData = new DocumentData
                {
                    Title = doc.Title,
                    RevitVersion = doc.Application.VersionNumber,
                    SourceFileName = doc.PathName ?? ""
                };

                _isUploading = true;

                var capturedHandle = formHandle;
                var capturedIfcPath = ifcPath;
                var lynxUrl = settings.LynxUrl;

                Task.Run(async () =>
                {
                    try
                    {
                        capturedHandle.SetStatus("Отправка на сервер...");
                        var result = await UploadIfcToServerAsync(capturedIfcPath, settings, docData, capturedHandle);
                        if (result.Success)
                        {
                            capturedHandle.SetCompleted(true, "Модель отправлена");

                            if (!string.IsNullOrEmpty(lynxUrl))
                            {
                                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(lynxUrl) { UseShellExecute = true });
                            }
                        }
                        else
                        {
                            capturedHandle.SetCompleted(false, $"Ошибка: {result.ErrorMessage}");
                        }
                    }
                    catch (Exception ex)
                    {
                        capturedHandle.SetCompleted(false, ex.Message);
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
                if (formHandle != null && !formHandle.IsCompleted)
                {
                    formHandle.SetCompleted(false, ex.Message);
                }
                else
                {
                    TaskDialog.Show("Lynx", $"Ошибка: {ex.Message}");
                }
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

        private async Task<UploadResult> UploadIfcToServerAsync(string ifcPath, SettingsData settings, DocumentData docData, ProgressFormHandle progressHandle)
        {
            using (var client = new HttpClient())
            {
                client.Timeout = TimeSpan.FromMinutes(10);

                using (var multipart = new MultipartFormDataContent())
                {
                    multipart.Add(new StringContent(settings.ProjectId), "project_id");
                    multipart.Add(new StringContent(docData.Title), "model_name");
                    multipart.Add(new StringContent(settings.RulesetId), "ruleset_id");
                    multipart.Add(new StringContent("VIV"), "discipline");
                    multipart.Add(new StringContent(docData.RevitVersion), "revit_version");
                    multipart.Add(new StringContent("0.1.0"), "plugin_version");
                    multipart.Add(new StringContent(docData.SourceFileName), "source_file_name");

                    var fileInfo = new FileInfo(ifcPath);
                    var progressStream = new ProgressFileStream(ifcPath, (sent, total) =>
                    {
                        int pct = (int)(50 + (sent * 50.0 / total));
                        progressHandle.SetProgress(pct);
                    });

                    using (var fileContent = new StreamContent(progressStream))
                    {
                        fileContent.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream");
                        multipart.Add(fileContent, "file", Path.GetFileName(ifcPath));

                        var response = await client.PostAsync($"{settings.ServerUrl}/api/v1/models/upload", multipart);

                        progressHandle.SetProgress(100);

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

    public class DocumentData
    {
        public string Title { get; set; }
        public string RevitVersion { get; set; }
        public string SourceFileName { get; set; }
    }
}