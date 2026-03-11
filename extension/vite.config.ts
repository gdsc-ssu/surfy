import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';
import { viteStaticCopy } from 'vite-plugin-static-copy';

export default defineConfig(({ mode }) => {
  if (mode === 'background' || mode === 'content') {
    const entry = mode === 'background' 
      ? resolve(__dirname, 'src/background/service-worker.ts')
      : resolve(__dirname, 'src/content/content.ts');

    return {
      build: {
        emptyOutDir: false,
        lib: {
          entry,
          formats: ['iife'],
          name: 'surfy',
          fileName: () => `${mode}.js`,
        },
      },
    };
  }

  return {
    plugins: [
      react(),
      viteStaticCopy({
        targets: [
          {
            src: 'manifest.json',
            dest: '.',
          },
        ],
      }),
    ],
    build: {
      rollupOptions: {
        input: {
          sidepanel: resolve(__dirname, 'sidepanel.html'),
          offscreen: resolve(__dirname, 'offscreen.html'),
        },
      },
    },
  };
});
