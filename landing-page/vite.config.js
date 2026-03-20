import { resolve } from 'path';
import handlebars from 'vite-plugin-handlebars';

export default {
  root: '.',
  plugins: [
    handlebars({
      partialDirectory: resolve(__dirname, 'src/partials'),
    }),
  ],
  build: {
    outDir: 'dist',
  },
};
