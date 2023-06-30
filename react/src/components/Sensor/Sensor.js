import moment from "moment-timezone";
import "moment/locale/ja";
import reactStringReplace from 'react-string-replace';

import { valueText, dateText } from "../../lib/util";

const Sensor = ({ isReady, stat }) => {
    const loading = () => {
        return (
            <span className="display-1 align-middle ms-4">
                <span className="display-5">Loading...</span>
            </span>
        );
    };

    const sensorRow = (sensorData, unit) => {
        let date = moment(sensorData.time);

        return (
            <tr className="row">
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

    const outdoorStatus = (stat) => {
        let message = stat.outdoor_status.message
        message = reactStringReplace(message, 'm^2', (match, i) => (
                <span>m<sup>2</sup></span>
        ));
        
        if (stat.outdoor_status.message != null) {
            return <div>{message}</div>;
        }
    };

    const sensorInfo = (stat) => {
        return (
            <div data-testid="sensor-info">
                <table className="table">
                    <thead>
                        <tr className="row">
                            <th className="col-3">センサー</th>
                            <th colSpan="2" className="col-4">
                                値
                            </th>
                            <th colSpan="2" className="col-5">
                                最新更新日時
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {sensorRow(stat.sensor.temp[0], "℃")}
                        {sensorRow(stat.sensor.humi[0], "%")}
                        {sensorRow(stat.sensor.lux[0], "lx")}
                        {sensorRow(stat.sensor.solar_rad[0], <span>W/m<sup>2</sup></span>)}
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

export default Sensor;
