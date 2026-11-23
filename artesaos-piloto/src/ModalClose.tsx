export default function ModalClose({onClose,disabled=false}:{onClose:()=>void;disabled?:boolean}){
 return <button type="button" className="modal-close" aria-label="Fechar" title="Fechar" disabled={disabled} onClick={onClose}>×</button>;
}
