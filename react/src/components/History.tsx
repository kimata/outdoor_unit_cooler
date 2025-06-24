import React from "react";
import { Chart, CategoryScale, LinearScale, BarElement, Tooltip, ChartOptions } from "chart.js";
import { Bar } from "react-chartjs-2";

Chart.register(CategoryScale, LinearScale, BarElement, Tooltip);

import { ApiResponse } from "../lib/ApiResponse";

type Props = {
    isReady: boolean;
    stat: ApiResponse.Stat;
};

const History = React.memo(({ isReady, stat }: Props) => {
    const history = (watering_list: ApiResponse.Watering[]) => {
        const chartOptions: ChartOptions<any> = {
            responsive: true,
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
        };

        const chartData = {
            labels: Array.from(Array(7), (_, i) => (i == 6 ? "本日" : 6 - i + "日前")),
            datasets: [
                {
                    label: "散水量",
                    data: watering_list.map((watering) => watering["amount"].toFixed(1)).reverse(),
                    backgroundColor: "rgba(128, 128, 128, 0.6)",
                },
            ],
        };

        return (
            <div className="card-body">
                <div className="container">
                    <div className="row" data-testid="history-info">
                        <Bar options={chartOptions} data={chartData} />
                    </div>
                </div>
            </div>
        );
    };
    const loading = () => {
        return (
            <div className="card-body">
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
                    {isReady ? history(stat.watering) : loading()}
                </div>
            </div>
        </div>
    );
});

History.displayName = 'History';

export { History };
