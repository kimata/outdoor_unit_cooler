import moment from 'moment-timezone';

import { valueText, dateText } from "../../lib/util";

const AirConditioner = ({ isReady, ctrlStat }) => {
    const loading = () => {
        return (
            <span className="display-1 align-middle ms-4">
                <span className="display-5">Loading...</span>
            </span>
        )
    }
   
    const airconRow = (airconData) => {
        let date = moment(airconData.time);
        
        return (
            <tr>
                <td className="text-start">{airconData.name}</td>
                <td className="text-end">{valueText(airconData.value)}</td>
                <td className="text-start">W</td>
                <td className="text-center">{dateText(date)}</td>
                <td className="text-center">{date.fromNow()}</td>
            </tr>
        )
    }
    const coolerStatus = (ctrlStat) => {
        if (ctrlStat.cooler_status.message != null) {
            return (
                <div>
                    {ctrlStat.cooler_status.message}
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
                            <th>エアコン</th>
                            <th colspan="2">値</th>
                            <th colspan="2">最新更新日時</th>
                        </tr>
                    </thead>
                    <tbody>
                {
                    ctrlStat.sensor.power.map(airconRow)
                }
                    </tbody>
                </table>
                <div>{ coolerStatus(ctrlStat) }</div>
            </div>
        )
    };
    
    return (
        <div className="container mt-4">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">エアコン稼働状況</h4>
                    </div>
                    <div className="card-body">
                        { isReady ? sensorInfo(ctrlStat) : loading() }
                    </div>
                </div>
            </div>
        </div >      
    );
}

export default AirConditioner;
