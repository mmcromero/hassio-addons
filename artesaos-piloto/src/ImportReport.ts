export type ManufacturingImportReport = {
 title?: string;
 sourceFiles?: Array<{name:string;sha256:string}>;
 summary?: Record<string,unknown>;
 warnings?: string[];
 excluded?: Array<{code?:string;name?:string;sheet?:string;row?:number;reason?:string}>;
 unmatched?: Array<{key?:string;name?:string;reason?:string;candidateIds?:number[]}>;
 matches?: Array<{key:string;name:string;sheet:string;method:string;wooId:number|null;wooName:string|null;wooSku:string|null;variationIds:number[]}>;
};
