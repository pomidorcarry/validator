using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;

namespace LynxRevitPlugin
{
    public class ProgressFileStream : Stream
    {
        private readonly FileStream _inner;
        private readonly long _length;
        private readonly Action<long, long> _onProgress;
        private long _position;

        public ProgressFileStream(string path, Action<long, long> onProgress)
        {
            _inner = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 8192, useAsync: true);
            _length = _inner.Length;
            _onProgress = onProgress;
        }

        public override bool CanRead => true;
        public override bool CanSeek => true;
        public override bool CanWrite => false;
        public override long Length => _length;
        public override long Position { get => _position; set => _inner.Position = value; }

        public override int Read(byte[] buffer, int offset, int count)
        {
            int read = _inner.Read(buffer, offset, count);
            _position += read;
            _onProgress?.Invoke(_position, _length);
            return read;
        }

        public override IAsyncResult BeginRead(byte[] buffer, int offset, int count, AsyncCallback callback, object state)
        {
            var result = _inner.BeginRead(buffer, offset, count, r =>
            {
                _position += _inner.EndRead(r);
                _onProgress?.Invoke(_position, _length);
                callback?.Invoke(r);
            }, state);
            return result;
        }

        public override int EndRead(IAsyncResult asyncResult) => _inner.EndRead(asyncResult);

        public override Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken)
        {
            return _inner.ReadAsync(buffer, offset, count, cancellationToken).ContinueWith(t =>
            {
                int read = t.Result;
                _position += read;
                _onProgress?.Invoke(_position, _length);
                return read;
            }, cancellationToken);
        }

        public override long Seek(long offset, SeekOrigin origin) => _inner.Seek(offset, origin);
        public override void SetLength(long value) => _inner.SetLength(value);
        public override void Write(byte[] buffer, int offset, int count) => _inner.Write(buffer, offset, count);
        public override void Flush() => _inner.Flush();

        protected override void Dispose(bool disposing)
        {
            if (disposing) _inner.Dispose();
            base.Dispose(disposing);
        }
    }
}
