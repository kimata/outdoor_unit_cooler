import React, { useMemo } from "react";
import { Chart, CategoryScale, LinearScale, BarElement, Tooltip, ChartOptions } from "chart.js";
import { Bar } from "react-chartjs-2";

Chart.register(CategoryScale, LinearScale, BarElement, Tooltip);

import { ApiResponse } from "../lib/ApiResponse";

type Props = {
    isReady: boolean;
    stat: ApiResponse.Stat;
};

const History = React.memo(({ isReady, stat }: Props) => {
    // chartOptionsは変更されないのでメモ化
    const chartOptions: ChartOptions<any> = useMemo(() => ({
        responsive: true,
        maintainAspectRatio: true,
        animation: {
            duration: 0 // アニメーションを無効化してちらつきを防止
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
    }), []);

    // chartDataのみstatの変更に応じて更新
    const chartData = useMemo(() => {
        if (!isReady || !stat.watering) {
            return null;
        }
        
        return {
            labels: Array.from(Array(7), (_, i) => (i == 6 ? "本日" : 6 - i + "日前")),
            datasets: [
                {
                    label: "散水量",
                    data: stat.watering.map((watering) => watering["amount"].toFixed(1)).reverse(),
                    backgroundColor: "rgba(128, 128, 128, 0.6)",
                },
            ],
        };
    }, [isReady, stat.watering]);

    const history = () => {
        return (
            <div className="card-body">
                <div className="w-100" data-testid="history-info">
                    {chartData && <Bar options={chartOptions} data={chartData} />}
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
            <div className="card-deck mb-0 text-center">
                <div className="card mb-0 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">散水履歴</h4>
                    </div>
                    {isReady ? history() : loading()}
                </div>
            </div>
        </div>
    );
});

History.displayName = 'History';

export { History };
