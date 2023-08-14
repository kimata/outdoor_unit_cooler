import { ApiResponse } from "../lib/ApiResponse";

type Props = {
    isReady: boolean;
    stat: ApiResponse.Stat;
};

const History = ({ isReady, stat }: Props) => {
    const history = (watering: ApiResponse.Watering[]) => {
        return (
            <div className="card-body outdoor_unit">
                <div className="container">
                    <div className="row"></div>
                </div>
            </div>
        );
    };
    const loading = () => {
        return (
            <div className="card-body outdoor_unit">
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
                    {isReady ? history(stat.watering) : loading()}
                </div>
            </div>
        </div>
    );
};

export { History };
