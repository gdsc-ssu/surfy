import { resolve } from 'path';
import handlebars from 'vite-plugin-handlebars';

const repositoryName = process.env.GITHUB_REPOSITORY?.split('/')[1] ?? '';
const defaultBase = repositoryName ? `/${repositoryName}/` : '/';
const base = process.env.VITE_BASE_PATH ?? defaultBase;

export default {
  root: '.',
  base,
  plugins: [
    handlebars({
      partialDirectory: resolve(__dirname, 'src/partials'),
    }),
  ],
  build: {
    outDir: 'dist',
  },
};
