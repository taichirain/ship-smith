import * as fs from 'fs';
import * as path from 'path';

export interface FlagsMap {
  [key: string]: boolean;
}

export interface FlagSyncOptions {
  flagsFilePath: string;
  cacheTTL?: number;
}

class FlagsClient {
  private flagsFilePath: string;
  private cacheTTL: number;
  private cachedFlags: FlagsMap | null = null;
  private lastLoadTime: number = 0;
  private mtime: number = 0;

  constructor(options: FlagSyncOptions) {
    this.flagsFilePath = options.flagsFilePath;
    this.cacheTTL = options.cacheTTL ?? 1000;
  }

  private loadFlags(): FlagsMap {
    try {
      const stats = fs.statSync(this.flagsFilePath);
      const currentMtime = stats.mtime.getTime();

      if (
        this.cachedFlags !== null &&
        currentMtime === this.mtime &&
        Date.now() - this.lastLoadTime < this.cacheTTL
      ) {
        return this.cachedFlags;
      }

      const content = fs.readFileSync(this.flagsFilePath, 'utf-8');
      const flags = JSON.parse(content) as FlagsMap;

      for (const key of Object.keys(flags)) {
        if (typeof flags[key] !== 'boolean') {
          flags[key] = false;
        }
      }

      this.cachedFlags = flags;
      this.lastLoadTime = Date.now();
      this.mtime = currentMtime;

      return flags;
    } catch (error) {
      this.cachedFlags = null;
      return {};
    }
  }

  isEnabled(key: string): boolean {
    const flags = this.loadFlags();
    return flags[key] === true;
  }

  getAllFlags(): FlagsMap {
    return { ...this.loadFlags() };
  }

  clearCache(): void {
    this.cachedFlags = null;
    this.lastLoadTime = 0;
    this.mtime = 0;
  }
}

let defaultClient: FlagsClient | null = null;

export function createFlagsClient(options: FlagSyncOptions): FlagsClient {
  return new FlagsClient(options);
}

export function init(options: FlagSyncOptions): void {
  defaultClient = new FlagsClient(options);
}

export function isEnabled(key: string): boolean {
  if (!defaultClient) {
    return false;
  }
  return defaultClient.isEnabled(key);
}

export function getAllFlags(): FlagsMap {
  if (!defaultClient) {
    return {};
  }
  return defaultClient.getAllFlags();
}

export { FlagsClient };
