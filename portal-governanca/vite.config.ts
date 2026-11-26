import {defineConfig} from "vite";
export default defineConfig({base:"./",server:{host:"127.0.0.1",proxy:{"/api":{target:"http://127.0.0.1:4174",changeOrigin:false}}}});
