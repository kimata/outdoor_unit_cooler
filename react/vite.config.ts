import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import macrosPlugin from "vite-plugin-babel-macros"

// https://vitejs.dev/config/
export default defineConfig({
    base: "/unit_cooler/",
    plugins: [
        react(),
        macrosPlugin(),
    ],
})
