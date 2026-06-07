import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const htmlPath = resolve(__dirname, '../../index.html');
const html = readFileSync(htmlPath, 'utf-8');

// Extract body content (skip <!DOCTYPE> and <html>/<head> wrappers)
const bodyMatch = html.match(/<body>([\s\S]*)<\/body>/i);
if (bodyMatch) {
  document.body.innerHTML = bodyMatch[1];
}
