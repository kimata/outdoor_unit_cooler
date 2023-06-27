import moment from "moment-timezone";

import { valueText, dateText } from "../../lib/util";

const AirConditioner = ({ isReady, stat }) => {
    const loading = () => {
        return (
            <span className="display-1 align-middle ms-4">
                <span className="display-5">Loading...</span>
            </span>
        );
    };

    const valueInt = (value) => {
        if (value == null) {
            return 0;
        } else {
            return parseInt(value);
        }
    };

    type AirconRowProps = { airconData: any };
    const AirconRow: React.FC<AirconRowProps> = (props) => {
        let date = moment(props.airconData.time);

        return (
            <tr key="{index}" className="row">
                <td className="text-start col-3 text-wrap">{props.airconData.name}</td>
                <td className="text-end col-4">
                    <div className="progress-label-container">
                        <div className="progress" style={{ height: "2em" }}>
                            <div
                                className="progress-bar bg-secondary"
                                role="progressbar"
                                aria-valuenow={valueInt(props.airconData.value)}
                                aria-valuemin="0"
                                aria-valuemax="1200"
                                style={{ width: (100.0 * props.airconData.value) / 1500 + "%" }}
                            ></div>
                        </div>
                        <div className="progress-label digit">
                            <b>{valueText(props.airconData.value,0)}</b>
                            <small className="ms-2">W</small>
                        </div>
                    </div>
                </td>
                <td className="text-start col-2">{date.fromNow()}</td>
                <td className="text-end col-3 text-wrap">
                    <small>{dateText(date)}</small>
                </td>
            </tr>
        );
    };
    const coolerStatus = (stat) => {
        if (stat.cooler_status.message != null) {
            return <div>{stat.cooler_status.message}</div>;
        }
    };

    const sensorInfo = (stat) => {
        return (
            <div data-testid="aircon-info">
                <table className="table">
                    <thead>
                        <tr className="row">
                            <th className="col-3">エアコン</th>
                            <th className="col-4">値</th>
                            <th colSpan="2" className="col-5">
                                最新更新日時
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {stat.sensor.power.map((airconData, index) => (
                            <AirconRow airconData={airconData} key={index} />
                        ))}
                    </tbody>
                </table>
                <div className="text-start">{coolerStatus(stat)}</div>
            </div>
        );
    };

    return (
        <div className="col">
            <div className="card-deck mb-3 text-center">
                <div className="card mb-4 shadow-sm">
                    <div className="card-header">
                        <h4 className="my-0 font-weight-normal">エアコン稼働状況</h4>
                    </div>
                    <div className="card-body">{isReady ? sensorInfo(stat) : loading()}</div>
                </div>
            </div>
        </div>
    );
};

export default AirConditioner;
