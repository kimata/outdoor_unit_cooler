import "dayjs/locale/ja";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
dayjs.locale("ja");
dayjs.extend(relativeTime);

import reactStringReplace from "react-string-replace";

import { valueText, dateText } from "../lib/Util";
import { ApiResponse } from "../lib/ApiResponse";

type Props = {
    isReady: boolean;
    stat: ApiResponse.Stat;
};

const Sensor = ({ isReady, stat }: Props) => {
    const loading = () => {
        return (
            <span className="display-1 align-middle ms-4">
                <span className="display-5">Loading...</span>
            </span>
        );
    };

    const sensorRow = (label: string, sensorData: ApiResponse.SensorData, unit: React.JSX.Element) => {
        let date = dayjs(sensorData.time);

        return (
            <tr className="row" key={label}>
                <td className="text-start col-3 text-nowrap">{sensorData.name}</td>
                <td className="text-end col-2 digit">
                    <b>{valueText(sensorData.value)}</b>
                </td>
                <td className="text-start col-2">
                    <small>{unit}</small>
                </td>
                <td className="text-start col-2">{date.fromNow()}</td>
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
                            <th className="col-3">センサー</th>
                            <th colSpan={2} className="col-4">
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
                    <div className="card-body">{isReady ? sensorInfo(stat) : loading()}</div>
                </div>
            </div>
        </div>
    );
};

export { Sensor };
