import { ref, type Ref } from "vue";

export type QueryLoader<T> = (signal: AbortSignal) => Promise<T>;

export type QueryResource<T> = {
  data: Ref<T | null>;
  error: Ref<Error | null>;
  loading: Ref<boolean>;
  reload: () => Promise<T | null>;
  retry: () => Promise<T | null>;
  abort: () => void;
};

export function createQueryResource<T>(loader: QueryLoader<T>): QueryResource<T> {
  const data = ref<T | null>(null) as Ref<T | null>;
  const error = ref<Error | null>(null);
  const loading = ref(false);
  let version = 0;
  let controller: AbortController | null = null;

  async function reload(): Promise<T | null> {
    version += 1;
    const requestVersion = version;
    controller?.abort();
    controller = new AbortController();
    loading.value = true;
    error.value = null;
    try {
      const result = await loader(controller.signal);
      if (requestVersion === version) {
        data.value = result;
        error.value = null;
      }
      return result;
    } catch (caught) {
      if (requestVersion === version) {
        error.value = caught instanceof Error ? caught : new Error(String(caught));
      }
      return null;
    } finally {
      if (requestVersion === version) {
        loading.value = false;
      }
    }
  }

  function abort(): void {
    controller?.abort();
    loading.value = false;
  }

  return {
    data,
    error,
    loading,
    reload,
    retry: reload,
    abort,
  };
}
