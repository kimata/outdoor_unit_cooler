import React from "react";
import "dayjs/locale/ja";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
dayjs.locale("ja");
dayjs.extend(relativeTime);

import reactStringReplace from "react-string-replace";

import { dateText } from "../lib/Util";
import { ApiResponse } from "../lib/ApiResponse";
import { AnimatedNumber } from "./common/AnimatedNumber";

type Props = {
    isReady: boolean;
    stat: ApiResponse.Stat;
};

const Sensor = React.memo(({ isReady, stat }: Props) => {
    const loading = () => {
        return (
            <span className="display-1 align-middle ms-4">
                <span className="display-5">Loading...</span>
            </span>
        );
    };

    const sensorRow = (label: string, sensorData: ApiResponse.SensorData, unit: React.JSX.Element) => {
        let date = dayjs(sensorData.time);

        // 照度・日射量の場合は値に応じて小数点桁数を調整
        const decimals = (label === "lux" && sensorData.value >= 10) || (label === "solar_rad" && sensorData.value >= 10) ? 0 : 1;

        return (
            <tr className="row" key={label}>
                <td className="text-start col-4" style={{overflow: 'visible', whiteSpace: 'nowrap'}}>{sensorData.name}</td>
                <td className="text-end col-3">
                    <div className="sensor-value" style={{whiteSpace: 'nowrap'}}>
                        <div className="sensor-number digit">
                            <b>
                                <AnimatedNumber
                                    value={sensorData.value || 0}
                                    decimals={decimals}
                                    useComma={label === "lux"}
                                />
                            </b>
                        </div>
                        <div className="sensor-unit" style={{whiteSpace: 'nowrap'}}>
                            <small>{unit}</small>
                        </div>
                    </div>
                </td>
                <td className="text-end col-2">{date.fromNow()}</td>
                <td className="text-start col-3 text-nowrap">
                    <small>{dateText(date)}</small>
                </td>
            </tr>
        );
    };

    const outdoorStatus = (stat: ApiResponse.Stat) => {
        if (stat.outdoor_status.message == null) {
            return;
        }

        let message = reactStringReplace(stat.outdoor_status.message, "m^2", () => (
            <span>
                m<sup>2</sup>
            </span>
        ));

        return <div>{message}</div>;
    };

    const sensorInfo = (stat: ApiResponse.Stat) => {
        return (
            <div data-testid="sensor-info">
                <table className="table">
                    <thead>
                        <tr className="row">
                            <th className="col-4">センサー</th>
                            <th className="col-3">
                                値
                            </th>
                            <th colSpan={2} className="col-5">
                                最新更新日時
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {sensorRow("temp", stat.sensor.temp[0], <span>℃</span>)}
                        {sensorRow("humi", stat.sensor.humi[0], <span>%</span>)}
                        {sensorRow("lux", stat.sensor.lux[0], <span>lx</span>)}
                        {sensorRow(
                            "solar_rad",
                            stat.sensor.solar_rad[0],
                            <span>
                                W/m<sup>2</sup>
                            </span>
                        )}
                        {sensorRow("rain", stat.sensor.rain[0], <span>mm/h</span>)}
                    </tbody>
                </table>
                <div className="text-start">{outdoorStatus(stat)}</div>
            </div>
        );
    };

    return (
        <div className="col">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">センサー値</h4>
                    </div>
                    <div className="card-body">{isReady || stat.sensor.temp.length > 0 ? sensorInfo(stat) : loading()}</div>
                </div>
            </div>
        </div>
    );
});

Sensor.displayName = 'Sensor';

export { Sensor };
