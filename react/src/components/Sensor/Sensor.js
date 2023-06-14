import moment from 'moment-timezone';
import 'moment/locale/ja';

import { valueText, dateText } from "../../lib/util";

const Sensor = ({ isReady, ctrlStat }) => {
    const loading = () => {
        return (
            <span className="display-1 align-middle ms-4">
                <span className="display-5">Loading...</span>
            </span>
        )
    }
    
    const sensorRow = (sensorData, unit) => {
        let date = moment(sensorData.time);
        
        return (
            <tr>
                <td className="text-start">{sensorData.name}</td>
                <td className="text-end">{valueText(sensorData.value)}</td>
                <td className="text-start">{unit}</td>
                <td className="text-center">{dateText(date)}</td>
                <td className="text-center">{date.fromNow()}</td>
            </tr>
        )
    }
    
    const outdoorStatus = (ctrlStat) => {
        if (ctrlStat.outdoor_status.message != null) {
            return (
                <div>
                    {ctrlStat.outdoor_status.message}
                </div>
            )
        }
    }
    
    const sensorInfo = (ctrlStat) => {
        return (
            <div>
                <table className="table">
                    <thead>
                        <tr>
                            <th>センサー</th>
                            <th colspan="2">値</th>
                            <th colspan="2">最新更新日時</th>
                        </tr>
                    </thead>
                    <tbody>
                        { sensorRow(ctrlStat.sensor.temp[0], "℃") }
                        { sensorRow(ctrlStat.sensor.humi[0], "%") }
                        { sensorRow(ctrlStat.sensor.lux[0], "lx") }
                        { sensorRow(ctrlStat.sensor.solar_rad[0], "W/m^2") }
                    </tbody>
                </table>
                <div>{ outdoorStatus(ctrlStat) }</div>
            </div>
        )
    };
    
    return (
        <div className="container mt-4">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">センサー値</h4>
                    </div>
                    <div className="card-body">
                        { isReady ? sensorInfo(ctrlStat) : loading() }
                    </div>
                </div>
            </div>
        </div >      
    );
}

export default Sensor;
