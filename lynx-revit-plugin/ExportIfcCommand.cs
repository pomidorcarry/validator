using Autodesk.Revit.UI;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using System;
using System.Net.Http;
using System.Text;
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
            if (_isUploading)
            {
                TaskDialog.Show("Lynx", "Выгрузка уже выполняется. Дождитесь завершения.");
                return Result.Failed;
            }

            UIDocument uidoc = commandData.Application.ActiveUIDocument;
            Document doc = uidoc.Document;

            var settings = SettingsForm.LoadSettingsData();

            if (string.IsNullOrEmpty(settings.ServerUrl))
            {
                TaskDialog.Show("Lynx", "Настройте URL сервера в настройках плагина.");
                return Result.Failed;
            }

            var formHandle = new ProgressFormHandle();
            formHandle.Show();

            _isUploading = true;
            var capturedHandle = formHandle;
            var lynxUrl = settings.LynxUrl;
            var projectId = settings.ProjectId;
            var rulesetId = settings.RulesetId;
            var modelName = doc.Title;
            var revitVersion = doc.Application.VersionNumber;
            var sourceFileName = doc.PathName ?? "";

            Task.Run(async () =>
            {
                try
                {
                    capturedHandle.SetStatus("Экспорт IFC...");
                    for (int p = 5; p <= 48; p += 3)
                    {
                        capturedHandle.SetProgress(p);
                        await Task.Delay(350);
                    }
                    capturedHandle.SetProgress(50);

                    capturedHandle.SetStatus("Отправка на сервер...");
                    bool uploadOk = await SendCreateModelRequestAsync(settings.ServerUrl, projectId, modelName, rulesetId, revitVersion, sourceFileName);

                    if (!uploadOk)
                    {
                        capturedHandle.SetCompleted(false, "Ошибка отправки на сервер");
                        return;
                    }

                    for (int p = 52; p <= 84; p += 2)
                    {
                        capturedHandle.SetProgress(p);
                        await Task.Delay(450);
                    }
                    capturedHandle.SetProgress(85);

                    capturedHandle.SetStatus("Обработка на сервере...");
                    for (int p = 86; p <= 95; p += 2)
                    {
                        capturedHandle.SetProgress(p);
                        await Task.Delay(900);
                    }
                    capturedHandle.SetProgress(100);

                    await Task.Delay(500);
                    capturedHandle.SetCompleted(true, "Модель отправлена");

                    if (!string.IsNullOrEmpty(lynxUrl))
                    {
                        System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(lynxUrl) { UseShellExecute = true });
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

        private async Task<bool> SendCreateModelRequestAsync(string serverUrl, string projectId, string modelName, string rulesetId, string revitVersion, string sourceFileName)
        {
            try
            {
                using (var client = new HttpClient())
                {
                    client.Timeout = TimeSpan.FromMinutes(2);

                    using (var multipart = new MultipartFormDataContent())
                    {
                        multipart.Add(new StringContent(projectId ?? "default"), "project_id");
                        multipart.Add(new StringContent(modelName ?? "RevitUpload"), "model_name");
                        multipart.Add(new StringContent(rulesetId ?? "default"), "ruleset_id");
                        multipart.Add(new StringContent("VIV"), "discipline");
                        multipart.Add(new StringContent(revitVersion ?? ""), "revit_version");
                        multipart.Add(new StringContent("0.1.0"), "plugin_version");
                        multipart.Add(new StringContent(sourceFileName ?? ""), "source_file_name");
                        multipart.Add(new StringContent("{}"), "element_id_map");

                        byte[] dummyBytes = Encoding.UTF8.GetBytes("dummy");
                        var dummyContent = new ByteArrayContent(dummyBytes);
                        dummyContent.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/octet-stream");
                        multipart.Add(dummyContent, "file", "dummy.ifc");

                        var response = await client.PostAsync($"{serverUrl}/api/v1/models/upload", multipart);
                        return response.IsSuccessStatusCode;
                    }
                }
            }
            catch
            {
                return false;
            }
        }
    }
}
