import {describe,expect,it} from "vitest";
import {getIngressBasePath,isIngressPeer,isLoopbackPeer,normalizePeerAddress,stripIngressPath} from "../server/ingress.mjs";
describe("fronteira de confiança do Home Assistant Ingress",()=>{
 it("normaliza IPv4 mapeado em IPv6 e valida o peer real",()=>{
  expect(normalizePeerAddress("::ffff:172.30.32.2")).toBe("172.30.32.2");
  expect(isIngressPeer("172.30.32.2")).toBe(true);
  expect(isIngressPeer("172.30.32.3")).toBe(false);
  expect(isIngressPeer("127.0.0.1")).toBe(false);
  expect(isLoopbackPeer("::ffff:127.0.0.1")).toBe(true);
 });
 it("aceita somente o prefixo de Ingress com um segmento de token",()=>{
  expect(getIngressBasePath("/api/hassio_ingress/opaque-token_123")).toBe("/api/hassio_ingress/opaque-token_123");
  expect(getIngressBasePath("/api/hassio_ingress/opaque-token_123/")).toBe("/api/hassio_ingress/opaque-token_123");
  expect(getIngressBasePath("/api/other/opaque-token")).toBeNull();
  expect(getIngressBasePath("/api/hassio_ingress/token/extra")).toBeNull();
  expect(getIngressBasePath("/api/hassio_ingress/../admin")).toBeNull();
  expect(getIngressBasePath("/api/hassio_ingress/.")).toBeNull();
  expect(getIngressBasePath(undefined)).toBeNull();
 });
 it("remove somente o prefixo exato quando o proxy o preserva",()=>{
  const base="/api/hassio_ingress/token-123";
  expect(stripIngressPath(base,base)).toBe("/");
  expect(stripIngressPath(base+"/",base)).toBe("/");
  expect(stripIngressPath(base+"/assets/app.js",base)).toBe("/assets/app.js");
  expect(stripIngressPath(base+"/api/health",base)).toBe("/api/health");
  expect(stripIngressPath("/api/hassio_ingress/token-123x/api/health",base)).toBeNull();
  expect(stripIngressPath("/api/hassio_ingress/other/api/health",base)).toBeNull();
 });
 it("preserva caminhos relativos à aplicação quando o proxy já removeu o prefixo",()=>{
  const base="/api/hassio_ingress/token-123";
  expect(stripIngressPath("/",base)).toBe("/");
  expect(stripIngressPath("//",base)).toBe("/");
  expect(stripIngressPath("/assets/app.js",base)).toBe("/assets/app.js");
  expect(stripIngressPath("/api/health",base)).toBe("/api/health");
  expect(stripIngressPath("/projects/avisaqui",base)).toBe("/projects/avisaqui");
  expect(stripIngressPath("api/health",base)).toBeNull();
 });
});
