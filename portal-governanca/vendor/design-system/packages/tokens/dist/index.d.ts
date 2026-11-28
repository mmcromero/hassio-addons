export interface TokenItem {
  value: string;
  type: string;
}

export declare const tokens: {
  ref: Record<string, TokenItem>;
  sys: Record<string, TokenItem>;
  themes: {
    dark: Record<string, TokenItem>;
    governance: Record<string, TokenItem>;
  };
};

export default tokens;
