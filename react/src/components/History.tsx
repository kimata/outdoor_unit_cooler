import React, { useMemo, useRef, useEffect } from "react";
import { Chart, CategoryScale, LinearScale, BarElement, Tooltip, ChartOptions } from "chart.js";
import { Bar } from "react-chartjs-2";

Chart.register(CategoryScale, LinearScale, BarElement, Tooltip);

import { ApiResponse } from "../lib/ApiResponse";

type Props = {
    isReady: boolean;
    stat: ApiResponse.Stat;
};

const History = React.memo(({ isReady, stat }: Props) => {
    const chartRef = useRef<Chart<"bar"> | null>(null);

    // chartOptionsは変更されないのでメモ化
    const chartOptions: ChartOptions<any> = useMemo(() => ({
        responsive: true,
        maintainAspectRatio: false,
        animation: {
            duration: 400, // 軽いアニメーションで値の変化を表現
        },
        scales: {
            y: {
                ticks: {
                    callback: function (value: any) {
                        return value + " L";
                    },
                },
                title: {
                    text: "散水量",
                    display: true,
                },
            },
        },
        plugins: {
            tooltip: {
                callbacks: {
                    label: function(context: any) {
                        return context.dataset.label + ': ' + context.parsed.y + ' L';
                    }
                }
            }
        },
    }), []);

    // 初期データ
    const initialChartData = useMemo(() => ({
        labels: Array.from(Array(7), (_, i) => (i == 6 ? "本日" : 6 - i + "日前")),
        datasets: [
            {
                label: "散水量",
                data: [0, 0, 0, 0, 0, 0, 0],
                backgroundColor: "rgba(128, 128, 128, 0.6)",
            },
        ],
    }), []);

    // データが更新された時にチャートを更新
    useEffect(() => {
        if (chartRef.current && isReady && stat.watering && stat.watering.length >= 7) {
            const chart = chartRef.current;
            const newData = stat.watering.map((watering) => parseFloat(watering["amount"].toFixed(1))).reverse();

            // データセットのデータのみ更新
            chart.data.datasets[0].data = newData;
            chart.update('none'); // アニメーションなしで更新
        }
    }, [isReady, stat.watering]);

    const history = () => {
        return (
            <div className="card-body">
                <div className="w-100" data-testid="history-info" style={{ height: '250px', position: 'relative' }}>
                    <Bar
                        ref={chartRef}
                        options={chartOptions}
                        data={initialChartData}
                    />
                </div>
            </div>
        );
    };
    const loading = () => {
        return (
            <div className="card-body">
                <span className="display-1 align-middle ms-4">
                    <span className="display-5">Loading...</span>
                </span>
            </div>
        );
    };

    return (
        <div className="col">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">散水履歴</h4>
                    </div>
                    {isReady || stat.watering.length > 0 ? history() : loading()}
                </div>
            </div>
        </div>
    );
});

History.displayName = 'History';

export { History };
