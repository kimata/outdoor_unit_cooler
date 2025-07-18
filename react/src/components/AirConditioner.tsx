import React, { useState, useEffect } from "react";
import "dayjs/locale/ja";
import dayjs, { locale, extend } from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
locale("ja");
extend(relativeTime);

import { motion } from "framer-motion";
import { dateText } from "../lib/Util";
import { ApiResponse } from "../lib/ApiResponse";
import { Loading } from "./common/Loading";
import { AnimatedNumber } from "./common/AnimatedNumber";

type Props = {
    isReady: boolean;
    stat: ApiResponse.Stat;
};

const AirConditioner = React.memo(({ isReady, stat }: Props) => {

    const valueInt = (value: number | null) => {
        if (value == null) {
            return 0;
        }

        if (typeof value === "string") {
            return parseInt(value);
        } else {
            return value;
        }
    };

    type AirconRowProps = { airconData: ApiResponse.SensorData };
    const AirconRow: React.FC<AirconRowProps> = React.memo((props) => {
        const [previousValue, setPreviousValue] = useState(props.airconData.value || 0);
        const currentWidth = (100.0 * props.airconData.value) / 1500;
        const previousWidth = (100.0 * previousValue) / 1500;

        useEffect(() => {
            setPreviousValue(props.airconData.value || 0);
        }, [props.airconData.value]);

        let date = dayjs(props.airconData.time);

        return (
            <tr key="{index}" className="row">
                <td className="text-start col-3 text-nowrap">{props.airconData.name}</td>
                <td className="text-end col-4">
                    <div className="progress-label-container">
                        <div className="progress" style={{ height: "2em" }}>
                            <motion.div
                                className="progress-bar bg-secondary"
                                role="progressbar"
                                aria-valuenow={valueInt(props.airconData.value)}
                                aria-valuemin={0}
                                aria-valuemax={1200}
                                initial={{ width: previousWidth + "%" }}
                                animate={{ width: currentWidth + "%" }}
                                transition={{ duration: 30.0, ease: "easeOut" }}
                            ></motion.div>
                        </div>
                        <div className="progress-label digit">
                            <b>
                                <AnimatedNumber
                                    value={props.airconData.value || 0}
                                    decimals={0}
                                    useComma={true}
                                />
                            </b>
                            <small className="ms-2">W</small>
                        </div>
                    </div>
                </td>
                <td className="text-start col-2">{date.fromNow()}</td>
                <td className="text-start col-3 text-nowrap">
                    <small>{dateText(date)}</small>
                </td>
            </tr>
        );
    });
    const coolerStatus = (stat: ApiResponse.Stat) => {
        if (stat.cooler_status.message != null) {
            return <div>{stat.cooler_status.message}</div>;
        }
    };

    const sensorInfo = (stat: ApiResponse.Stat) => {
        return (
            <div data-testid="aircon-info">
                <table className="table">
                    <thead>
                        <tr className="row">
                            <th className="col-3">エアコン</th>
                            <th className="col-4">値</th>
                            <th colSpan={2} className="col-5">
                                最新更新日時
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {stat.sensor.power.map((airconData: ApiResponse.SensorData, index: number) => (
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
                    <div className="card-body">{isReady || stat.sensor.power.length > 0 ? sensorInfo(stat) : <Loading size="large" />}</div>
                </div>
            </div>
        </div>
    );
});

AirConditioner.displayName = 'AirConditioner';

export { AirConditioner };
