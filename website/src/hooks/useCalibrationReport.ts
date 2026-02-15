import { useQuery } from '@tanstack/react-query';
import type { CalibrationReport } from '../../types';

async function fetchCalibrationReport(): Promise<CalibrationReport> {
  const response = await fetch('/data/calibration-report.json');
  if (!response.ok) {
    throw new Error(`Failed to load calibration report: ${response.status}`);
  }
  return (await response.json()) as CalibrationReport;
}

export function useCalibrationReport() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['calibration-report'],
    queryFn: fetchCalibrationReport,
    staleTime: 1000 * 60 * 5,
  });

  return {
    report: data ?? null,
    loading: isLoading,
    error: error ? (error instanceof Error ? error.message : 'Failed to load calibration report') : null,
  };
}

export default useCalibrationReport;
