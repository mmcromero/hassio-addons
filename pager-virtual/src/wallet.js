import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Credenciais privadas nunca entram na imagem ou no repositório.
// Prioridade: variável em memória > arquivo explícito > configuração do add-on (/config) > /data persistente > legado local.
function loadWalletCredentials() {
  const inline = process.env.GOOGLE_WALLET_CREDENTIALS;
  const customFile = process.env.GOOGLE_WALLET_KEY_FILE;
  const dataDir = process.env.DATA_PATH || '/data';
  const candidates = inline !== undefined
    ? [{ source: 'environment', value: inline }]
    : (customFile !== undefined
        ? [{ source: 'file', value: customFile }]
        : [
            { source: 'file', value: '/config/google-wallet-key.json' },
            { source: 'file', value: path.join(dataDir, 'credentials/google-wallet-key.json') },
            { source: 'file', value: path.join(__dirname, '../credentials/google-wallet-key.json') }
          ]);
  for (const candidate of candidates) {
    try {
      let value;
      if (candidate.source === 'environment') {
        value = candidate.value;
      } else {
        // Um caminho explícito inválido não deve fazer fallback para outra chave.
        if (typeof candidate.value !== 'string' || !path.isAbsolute(candidate.value) ||
            candidate.value.includes(String.fromCharCode(0))) break;
        if (!fs.existsSync(candidate.value)) continue;
        value = fs.readFileSync(candidate.value, 'utf8');
      }
      const parsed = JSON.parse(value);
      if (typeof parsed?.private_key === 'string' &&
          typeof parsed?.client_email === 'string' && parsed.private_key.trim() &&
          parsed.client_email.trim()) return parsed;
    } catch {
      // Não registrar conteúdo, caminho ou erro bruto: podem conter segredos.
    }
    // Não usar outra fonte após uma fonte encontrada, porém inválida.
    break;
  }
  return null;
}

const credentials = loadWalletCredentials();

const ISSUER_ID = process.env.GOOGLE_WALLET_ISSUER_ID || '3388000000023241721';

function base64UrlEncode(str) {
  const buffer = Buffer.isBuffer(str) ? str : Buffer.from(str);
  return buffer.toString('base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
}

export function signJwt(header, payload, privateKeyPem) {
  const encHeader = base64UrlEncode(JSON.stringify(header));
  const encPayload = base64UrlEncode(JSON.stringify(payload));
  const data = `${encHeader}.${encPayload}`;
  const signer = crypto.createSign('RSA-SHA256');
  signer.update(data);
  const signature = signer.sign(privateKeyPem);
  return `${data}.${base64UrlEncode(signature)}`;
}

/**
 * Gera a URL oficial de "Salvar na Carteira do Google" para um pedido
 */
export function generateSaveUrl(pedido) {
  if (!credentials || !credentials.private_key) {
    throw new Error('Chave de serviço da Carteira do Google não configurada.');
  }

  const classId = `${ISSUER_ID}.avisaqui_comprovante_v1`;
  const objectId = `${ISSUER_ID}.${pedido.token || pedido.id}`;

  const claims = {
    iss: credentials.client_email,
    aud: 'google',
    origins: ['https://pay.google.com'],
    typ: 'savetowallet',
    iat: Math.floor(Date.now() / 1000),
    payload: {
      genericClasses: [
        {
          id: classId,
          issuerName: 'Avisaqui'
        }
      ],
      genericObjects: [
        {
          id: objectId,
          classId: classId,
          cardTitle: {
            defaultValue: {
              language: 'pt-BR',
              value: pedido.restaurante_nome || 'Avisaqui Pager'
            }
          },
          header: {
            defaultValue: {
              language: 'pt-BR',
              value: `Senha #${pedido.numero}`
            }
          },
          subheader: {
            defaultValue: {
              language: 'pt-BR',
              value: 'ACOMPANHAMENTO DO PEDIDO'
            }
          },
          textModulesData: [
            {
              id: 'status_pedido',
              header: 'Status Atual',
              body: pedido.status === 'pronto' ? 'PRONTO PARA RETIRADA!' : 'Em preparo na cozinha...'
            }
          ],
          hexBackgroundColor: '#0f172a',
          state: 'ACTIVE'
        }
      ]
    }
  };

  const header = {
    alg: 'RS256',
    typ: 'JWT'
  };

  const token = signJwt(header, claims, credentials.private_key);
  return `https://pay.google.com/gp/v/save/${token}`;
}

/**
 * Obtém token OAuth2 para chamadas da API REST do Google Wallet
 */
async function getGoogleAuthToken() {
  if (!credentials || !credentials.private_key) {
    throw new Error('Credenciais do Google não encontradas');
  }

  const now = Math.floor(Date.now() / 1000);
  const jwtPayload = {
    iss: credentials.client_email,
    scope: 'https://www.googleapis.com/auth/wallet_object.issuer',
    aud: 'https://oauth2.googleapis.com/token',
    exp: now + 3600,
    iat: now
  };

  const assertion = signJwt({ alg: 'RS256', typ: 'JWT' }, jwtPayload, credentials.private_key);

  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion
    })
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Falha na autenticação OAuth2 do Google: ${response.status} ${errorText}`);
  }

  const data = await response.json();
  return data.access_token;
}

/**
 * Atualiza o status do passe para PRONTO no Google Wallet
 * Isso acorda a tela de bloqueio e exibe a notificação do sistema
 */
export async function notifyGoogleWalletReady(pedido) {
  try {
    const accessToken = await getGoogleAuthToken();
    const objectId = `${ISSUER_ID}.${pedido.token || pedido.id}`;
    const url = `https://walletobjects.googleapis.com/walletobjects/v1/genericObject/${objectId}`;

    const patchBody = {
      header: {
        defaultValue: {
          language: 'pt-BR',
          value: `🔔 PRONTO! Senha #${pedido.numero}`
        }
      },
      textModulesData: [
        {
          id: 'status_pedido',
          header: 'Status Atual',
          body: 'Seu pedido está no balcão de entrega! Retire com a senha #' + pedido.numero
        }
      ],
      state: 'ACTIVE'
    };

    const res = await fetch(url, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(patchBody)
    });

    if (!res.ok) {
      // 404 significa que o usuário não salvou o comprovante na carteira dele (comportamento normal)
      if (res.status === 404) {
        return { updated: false, reason: 'pass_not_saved_by_user' };
      }
      const err = await res.text();
      console.warn(`[GoogleWallet] Falha ao atualizar passe ${objectId}:`, res.status, err);
      return { updated: false, error: err };
    }

    return { updated: true };
  } catch (err) {
    console.warn('[GoogleWallet] Erro na notificação:', err?.message || err);
    return { updated: false, error: err?.message };
  }
}
