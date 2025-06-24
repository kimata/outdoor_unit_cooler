import { useState, useEffect, useCallback } from 'react';

interface UseApiState<T> {
  data: T;
  loading: boolean;
  error: string | null;
}

interface UseApiOptions {
  interval?: number;
  immediate?: boolean;
}

export function useApi<T>(
  url: string,
  initialData: T,
  options: UseApiOptions = {}
): UseApiState<T> & { refetch: () => Promise<void> } {
  const [data, setData] = useState<T>(initialData);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (): Promise<void> => {
    try {
      // 初回のみloadingをtrueにする
      if (data === initialData) {
        setLoading(true);
      }
      setError(null);

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      setData(result);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '通信に失敗しました';
      setError(errorMessage);
      console.error('API fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [url, data, initialData]);

  useEffect(() => {
    if (options.immediate !== false) {
      fetchData();
    }

    if (options.interval) {
      const intervalId = setInterval(fetchData, options.interval);
      return () => clearInterval(intervalId);
    }
  }, [fetchData, options.immediate, options.interval]);

  return {
    data,
    loading,
    error,
    refetch: fetchData,
  };
}
