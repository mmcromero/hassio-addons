export type ProjectResourceStatus = "last_observed_active" | "historical" | "candidate" | "unverified";
export type ProjectResource = {
  id:string;
  projectId:string;
  kind:string;
  label:string;
  description:string;
  status:ProjectResourceStatus;
  observedAt:string;
  confidence:"repository_documented"|"owner_history"|"inferred";
  source:string;
  sourceUrl?:string;
  links:{label:string;url:string}[];
};

export const projectResourceRegistry:ProjectResource[] = [
  {
    id:"artesao-digital-public-origin",
    projectId:"artesao-digital",
    kind:"public_origin",
    label:"Domínio público oficial",
    description:"Origem oficial da aplicação: artesaodigital.com.br/artesaos-piloto/. O documento do projeto determina essa origem única; não presumir aliases ou outro host.",
    status:"last_observed_active",
    observedAt:"2026-11-04",
    confidence:"repository_documented",
    source:"mmcromero/fabricacao_e_orcamentos — apps/umdoislab/distribution/docs/DOMINIO-PUBLICO.md",
    sourceUrl:"https://github.com/mmcromero/fabricacao_e_orcamentos/blob/5d691d65814079567048ad6ee59e281250d61ff4/apps/umdoislab/distribution/docs/DOMINIO-PUBLICO.md",
    links:[{label:"Abrir aplicação",url:"https://artesaodigital.com.br/artesaos-piloto/"}]
  },
  {
    id:"artesao-digital-cloudflare-tunnel",
    projectId:"artesao-digital",
    kind:"cloudflare_tunnel",
    label:"Cloudflare Tunnel · forja-01-artesao",
    description:"Último registro operacional: cloudflared.service ativo no Forja 01; encaminhamento conhecido para 127.0.0.1:8099. A observação não substitui uma consulta atual ao host e ao painel Cloudflare.",
    status:"last_observed_active",
    observedAt:"2026-11-26",
    confidence:"owner_history",
    source:"Histórico operacional confirmado pelo proprietário; requer revalidação direta para afirmar estado atual.",
    links:[{label:"Abrir painel Cloudflare",url:"https://dash.cloudflare.com/"}]
  }
];

export function projectResourcesFor(projectId:string):ProjectResource[]{
  return projectResourceRegistry.filter(resource=>resource.projectId===projectId);
}
