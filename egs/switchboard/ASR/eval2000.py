
from itertools import chain
from pathlib import Path
from typing import Dict, Optional, Union

from lhotse import fix_manifests, validate_recordings_and_supervisions
from lhotse.audio import Recording, RecordingSet
from lhotse.supervision import SupervisionSegment, SupervisionSet
from lhotse.utils import Pathlike, check_and_rglob, urlretrieve_progress




def prepare_eval2000(
    audio_dir: Pathlike,
    transcripts_dir: Optional[Pathlike] = None,
    sentiment_dir: Optional[Pathlike] = None,
    output_dir: Optional[Pathlike] = None,
    omit_silence: bool = True,
    absolute_paths: bool = False,
) -> Dict[str, Union[RecordingSet, SupervisionSet]]:
    audio_paths = check_and_rglob(audio_dir, "*.sph")
    text_paths = check_and_rglob(transcripts_dir, "*.txt")

    groups = []
    name_to_text = {p.stem.split("-")[0]: p for p in text_paths}
    #print(name_to_text)
    for ap in audio_paths:
        name = ap.stem #.replace("sw", "eval")
        #name = ap.stem.replace("en", "eval")
        groups.append(
            {
                "audio": ap,
                "text": name_to_text[f"{name}"],
               # "text-1": name_to_text[f"{name}B"],
            }
        )

    recordings = RecordingSet.from_recordings(
        Recording.from_file(
            group["audio"], relative_path_depth=None if absolute_paths else 3
        )
        for group in groups
    )
    supervisions = SupervisionSet.from_segments(
        chain.from_iterable(
            make_segments(
                transcript_path=group[f"text"],
                recording=recording,
                channel=channel,
                omit_silence=omit_silence,
            )
            for group, recording in zip(groups, recordings)
            for channel in [0]
        )
    )

    recordings, supervisions = fix_manifests(recordings, supervisions)
    validate_recordings_and_supervisions(recordings, supervisions)

    if sentiment_dir is not None:
        parse_and_add_sentiment_labels(sentiment_dir, supervisions)

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        recordings.to_file(output_dir / "recordings_eval.jsonl")
        supervisions.to_file(output_dir / "supervisions_eval.jsonl")
    return {"recordings": recordings, "supervisions": supervisions}


def make_segments(
    transcript_path: Path, recording: Recording, channel: int, omit_silence: bool = True
):
    lines = transcript_path.read_text().splitlines()
    lines = list(filter(lambda line: len(line.split()) >= 4 and not line.startswith('#') , lines))
    lines = list(map(lambda i1: str(i1[0])+ " " +i1[1], list(enumerate(lines)) ) )
    return [
        SupervisionSegment(
            id=recording.id+'_'+segment_id,
            recording_id=recording.id,
            start=float(start),
            duration=round(float(end) - float(start), ndigits=8),
            channel=channel,
            text=" ".join(words),
            language="English",
            speaker=f"{recording.id}"+"_"+segment_id+"_"+speaker.replace(':',''),
        )
        for segment_id, start, end, speaker, *words in map(str.split, lines)
        if words[0] != "[silence]" or not omit_silence
    ]


def parse_and_add_sentiment_labels(
    sentiment_dir: Pathlike, supervisions: SupervisionSet
):
    """Read 'LDC2020T14' sentiment annotations and add then to the supervision segments."""
    import pandas as pd

    # Sanity checks
    sentiment_dir = Path(sentiment_dir)
    labels = sentiment_dir / "data" / "sentiment_labels.tsv"
    assert sentiment_dir.is_dir() and labels.is_file()
    # Read the TSV as a dataframe
    df = pd.read_csv(labels, delimiter="\t", names=["id", "start", "end", "sentiment"])
    # We are going to match the segments in LDC2020T14 with the ones we already
    # parsed from ISIP transcripts. We simply look which of the existing segments
    # fall into a sentiment-annotated time span. When doing it this way, we use
    # 51773 out of 52293 available sentiment annotations, which should be okay.
    for _, row in df.iterrows():
        call_id = row["id"].split("_")[0]
        matches = list(
            supervisions.find(
                recording_id=call_id,
                start_after=row["start"] - 1e-2,
                end_before=row["end"] + 1e-2,
            )
        )
        if not matches:
            continue
        labels = row["sentiment"].split("#")
        # SupervisionSegments returned from .find() are references to the ones in the
        # SupervisionSet, so we can just modify them. We use the "custom" field
        # to add the sentiment label. Since there were multiple annotators,
        # we add all available labels and leave it up to the user to disambiguate them.
        for segment in matches:
            segment.custom = {f"sentiment{i}": label for i, label in enumerate(labels)}

if __name__ == "__main__":
    prepare_eval2000("download/eval2000","download/eval2000_trans",None,"data/manifests",True,False)