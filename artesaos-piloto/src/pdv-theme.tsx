import {useState, type CSSProperties} from 'react';
import ActionButton from './ActionButton';
import './pdv.css';

const defaultColor = '#087429';

function storageKey() {
 const account = document.querySelector<HTMLMetaElement>('meta[name="pilot-context"]')?.content ?? 'local';
 return 'artesao-pdv-color:' + new URL('.', document.baseURI).pathname + ':' + account;
}

function readColor() {
 try {
  const color = localStorage.getItem(storageKey()) ?? '';
  return /^#[\da-f]{6}$/i.test(color) ? color : '';
 } catch {
  return '';
 }
}

export function pdvTheme(): CSSProperties | undefined {
 const color = readColor();
 if (!color) return;
 const channels = [1, 3, 5].map(offset => parseInt(color.slice(offset, offset + 2), 16) / 255);
 const [red, green, blue] = channels.map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
 const luminance = .2126 * red + .7152 * green + .0722 * blue;
 const lightText = luminance <= .179;
 return {
  '--pdv-accent': color,
  '--pdv-highlight': `color-mix(in srgb, ${color} 40%, #000)`,
  '--pdv-on-accent': lightText ? '#fff' : '#000',
  '--pdv-hover-base': lightText ? '#000' : '#fff',
 } as CSSProperties;
}

export function PdvColorSettings({onSaved}:{onSaved?:()=>void}={}) {
 const [saved, setSaved] = useState(readColor);
 const [color, setColor] = useState(saved || defaultColor);
 const [message, setMessage] = useState('');

 function save(next: string) {
  try {
   if (next) localStorage.setItem(storageKey(), next);
   else localStorage.removeItem(storageKey());
   setSaved(next);
   setColor(next || defaultColor);
   setMessage(next ? 'Cor do PDV salva.' : 'Cor padrão restaurada.');
   onSaved?.();
  } catch {
   setMessage('Não foi possível salvar a cor neste navegador.');
  }
 }

 return <section>
  <h3>Aparência do PDV</h3>
  <label>Cor principal do PDV
   <input type="color" value={color} onChange={event => {setColor(event.target.value);setMessage('');}}/>
  </label>
  <p>A preferência é salva neste navegador para sua conta.</p>
  <ActionButton type="button" disabled={color === (saved || defaultColor)} onClick={() => save(color)}>Salvar cor</ActionButton>
  <ActionButton type="button" disabled={!saved && color === defaultColor} onClick={() => save('')}>Restaurar padrão</ActionButton>
  <p role="status">{message}</p>
 </section>;
}
