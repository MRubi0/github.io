from celery import shared_task
from django.conf import settings
from django.shortcuts import get_object_or_404
from .models import Tour, Paso, TourRelation
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
import time
import logging
import json
import io
import unicodedata # For normalize_filename
import re # For normalize_filename
from datetime import datetime # For unique job names

logger = logging.getLogger(__name__)

# Helper functions (can be in a separate utils.py if they grow)
def normalize_filename_for_celery(filename):
    nfkd_form = unicodedata.normalize('NFKD', filename)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^0-9a-zA-Z._-]', '_', only_ascii)

def wait_for_transcription_job_completion(transcribe_client, job_name):
    max_attempts = 20 # Approx 10 minutes
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        status_response = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
        job_status = status_response['TranscriptionJob']['TranscriptionJobStatus']
        logger.debug(f"Transcription job {job_name} status: {job_status} (Attempt {attempt})")
        if job_status in ['COMPLETED', 'FAILED']:
            return status_response
        time.sleep(30)
    logger.error(f"Transcription job {job_name} timed out after {max_attempts * 30} seconds.")
    raise Exception(f"Transcription job {job_name} timed out.")


def get_transcription_text_from_s3(s3_client, bucket_name, key):
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        raw_data = response['Body'].read()
        encoding = 'utf-8' # Default, consider chardet if encodings vary significantly
        transcription_data = json.loads(raw_data.decode(encoding))
        return transcription_data.get('results', {}).get('transcripts', [{}])[0].get('transcript', '')
    except Exception as e:
        logger.error(f"Error retrieving or parsing transcription from S3 ({bucket_name}/{key}): {e}", exc_info=True)
        return f"Error retrieving transcription: {str(e)}"

@shared_task
def test_task():
    logger.info("Executing test_task from Celery.")
    return "Test task completed successfully!"

@shared_task(bind=True, max_retries=3, default_retry_delay=60) # Added bind, retries
def process_transcription_task(self, tour_id):
    logger.info(f"Starting transcription process for tour_id: {tour_id}")
    try:
        tour_og = get_object_or_404(Tour, pk=tour_id)

        if not tour_og.audio or not hasattr(tour_og.audio, 'name') or not tour_og.audio.name:
            logger.warning(f"Tour {tour_id} does not have a main audio file. Skipping main transcription.")
            # Update tour status if needed: tour_og.transcription_status = "NO_AUDIO"; tour_og.save()
        else:
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            region_name = settings.AWS_S3_REGION_NAME
            s3_client = boto3.client('s3', region_name=region_name)
            transcribe_client = boto3.client('transcribe', region_name=region_name)

            main_audio_s3_key = tour_og.audio.name
            main_job_name_base = normalize_filename_for_celery(f"{main_audio_s3_key.split('/')[-1].split('.')[0]}_{tour_og.user_id}_{tour_id}_main")
            main_job_name = f"{main_job_name_base}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            main_job_uri = f's3://{bucket_name}/{main_audio_s3_key}'
            main_output_key = f'transcriptions/{str(tour_id).zfill(5)}/{main_job_name}.json'

            lang_code_map = {'es': 'es-ES', 'en': 'en-US'}
            language_code = lang_code_map.get(tour_og.idioma, tour_og.idioma)

            logger.info(f"Starting main transcription job {main_job_name} for tour {tour_id}")
            transcribe_client.start_transcription_job(
                TranscriptionJobName=main_job_name,
                Media={'MediaFileUri': main_job_uri},
                MediaFormat=main_audio_s3_key.split('.')[-1],
                LanguageCode=language_code,
                OutputBucketName=bucket_name,
                OutputKey=main_output_key
            )
            # This task will now complete, and the waiting/processing happens elsewhere or not at all
            # If we need to wait and process, this task would be very long-running.
            # For now, let's assume starting the job is enough, and another mechanism checks status.
            # OR, make this task responsible for the whole lifecycle:
            wait_for_transcription_job_completion(transcribe_client, main_job_name)
            logger.info(f"Main transcription job {main_job_name} completed for tour {tour_id}.")
            # tour_og.main_transcription_s3_key = main_output_key (add such a field to Tour model)
            # tour_og.save()

        # Process steps
        pasos = Paso.objects.filter(tour=tour_og)
        for paso in pasos:
            if not paso.audio or not hasattr(paso.audio, 'name') or not paso.audio.name:
                logger.info(f"Paso {paso.step_number} for tour {tour_id} has no audio. Skipping.")
                continue

            paso_audio_s3_key = paso.audio.name
            paso_job_name_base = normalize_filename_for_celery(f"{paso_audio_s3_key.split('/')[-1].split('.')[0]}_{tour_og.user_id}_{tour_id}_step_{paso.step_number}")
            paso_job_name = f"{paso_job_name_base}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            paso_job_uri = f's3://{bucket_name}/{paso_audio_s3_key}'
            paso_output_key = f'transcriptions/{str(tour_id).zfill(5)}/steps/{str(paso.step_number).zfill(5)}/{paso_job_name}.json'

            logger.info(f"Starting step transcription job {paso_job_name} for tour {tour_id}, step {paso.step_number}")
            transcribe_client.start_transcription_job(
                TranscriptionJobName=paso_job_name,
                Media={'MediaFileUri': paso_job_uri},
                MediaFormat=paso_audio_s3_key.split('.')[-1],
                LanguageCode=language_code,
                OutputBucketName=bucket_name,
                OutputKey=paso_output_key
            )
            wait_for_transcription_job_completion(transcribe_client, paso_job_name)
            logger.info(f"Step transcription job {paso_job_name} completed for tour {tour_id}, step {paso.step_number}.")
            # paso.transcription_s3_key = paso_output_key (add such a field to Paso model)
            # paso.save()

        # Consolidate transcriptions (as in the original view)
        # This part is complex and might be better as a separate task triggered after all individual jobs complete.
        # For now, just logging completion of starting jobs.
        logger.info(f"All transcription jobs started for tour {tour_id}.")
        # To replicate original: retrieve all JSONs, combine, save to complete_transcription.txt
        # This is too long for one task; should be chained or handled by a monitoring process.

    except Tour.DoesNotExist:
        logger.error(f"Tour with id {tour_id} not found for transcription.", exc_info=True)
    except ClientError as e:
        logger.error(f"AWS ClientError in process_transcription_task for tour {tour_id}: {e}", exc_info=True)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Unexpected error in process_transcription_task for tour {tour_id}: {e}", exc_info=True)
        raise self.retry(exc=e) # Retry for generic errors too

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_translation_task(self, source_tour_id, target_tour_id, source_lang_code, target_lang_code):
    logger.info(f"Starting translation process for source_tour_id: {source_tour_id} to target_tour_id: {target_tour_id} ({source_lang_code} -> {target_lang_code})")
    try:
        source_tour = get_object_or_404(Tour, pk=source_tour_id)
        target_tour = get_object_or_404(Tour, pk=target_tour_id) # Ensure target tour exists

        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        region_name = settings.AWS_S3_REGION_NAME
        s3_client = boto3.client('s3', region_name=region_name)
        translate_client = boto3.client('translate', region_name=region_name)

        # Assuming consolidated transcription file exists for the source tour
        source_transcription_key = f'transcriptions/{str(source_tour.id).zfill(5)}/complete_transcription.txt'

        transcription_text = ""
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=source_transcription_key)
            transcription_text = response['Body'].read().decode('utf-8')
        except ClientError as e:
            logger.error(f"Failed to get transcription file {source_transcription_key} from S3: {e}", exc_info=True)
            raise self.retry(exc=e)

        if not transcription_text.strip():
            logger.warning(f"Source transcription for tour {source_tour_id} is empty. Skipping translation.")
            return "Source transcription empty."

        sections = transcription_text.split('########################################################################')
        translated_sections = []
        for section in sections:
            if section.strip():
                try:
                    response = translate_client.translate_text(
                        Text=section.strip(),
                        SourceLanguageCode=source_lang_code,
                        TargetLanguageCode=target_lang_code
                    )
                    translated_sections.append(response['TranslatedText'])
                except ClientError as e:
                    logger.error(f"AWS Translate error for section: {section[:50]}...", exc_info=True)
                    translated_sections.append(f"[Translation Error: {section[:50]}...]") # Keep original on error or mark error
            else:
                translated_sections.append('')

        translated_full_text = '\n########################################################################\n'.join(translated_sections)

        translated_output_key = f'transcriptions/{str(target_tour.id).zfill(5)}/complete_transcription_translated.txt'
        s3_client.put_object(Bucket=bucket_name, Key=translated_output_key, Body=translated_full_text, ContentType='text/plain')

        # Update target tour model with info about translated transcription (if such a field exists)
        # target_tour.translated_transcription_s3_key = translated_output_key
        # target_tour.save()
        logger.info(f"Translation completed for tour {source_tour_id} and saved to {translated_output_key} for target tour {target_tour_id}")
        return f"Translation successful. Output: {translated_output_key}"

    except Tour.DoesNotExist:
        logger.error(f"Tour not found in process_translation_task (source: {source_tour_id}, target: {target_tour_id}).", exc_info=True)
    except ClientError as e:
        logger.error(f"AWS ClientError in process_translation_task: {e}", exc_info=True)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Unexpected error in process_translation_task: {e}", exc_info=True)
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_synthesis_task(self, target_tour_id):
    logger.info(f"Starting speech synthesis for target_tour_id: {target_tour_id}")
    try:
        target_tour = get_object_or_404(Tour.objects.select_related('user'), pk=target_tour_id) # Assuming user might be needed for voice choice or path

        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        region_name = settings.AWS_S3_REGION_NAME
        s3_client = boto3.client('s3', region_name=region_name)
        polly_client = boto3.client('polly', region_name=region_name)

        transcription_key = f'transcriptions/{str(target_tour.id).zfill(5)}/complete_transcription_translated.txt'

        translated_text_content = ""
        try:
            response = s3_client.get_object(Bucket=bucket_name, Key=transcription_key)
            translated_text_content = response['Body'].read().decode('utf-8')
        except ClientError as e:
            logger.error(f"Failed to get translated transcription {transcription_key} from S3: {e}", exc_info=True)
            raise self.retry(exc=e)

        if not translated_text_content.strip():
            logger.warning(f"Translated transcription for tour {target_tour_id} is empty. Skipping synthesis.")
            return "Translated transcription empty."

        sections = translated_text_content.split('########################################################################')

        voice_id_map = {'es': 'Mia', 'en': 'Joanna'} # Example, make configurable
        voice_id = voice_id_map.get(target_tour.idioma, 'Joanna')

        # Synthesize main tour audio
        if sections and sections[0].strip() and "End Of File" not in sections[0]:
            main_text_to_synthesize = sections[0].strip()
            try:
                response = polly_client.synthesize_speech(Text=main_text_to_synthesize, OutputFormat='mp3', VoiceId=voice_id)
                audio_stream = response['AudioStream'].read()

                main_audio_key = f"Tour_audio/{str(target_tour.id).zfill(5)}/synth_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.mp3"
                if target_tour.audio and hasattr(target_tour.audio, 'name') and target_tour.audio.name:
                     boto3.client('s3').delete_object(Bucket=bucket_name, Key=target_tour.audio.name) # Delete old audio

                s3_client.put_object(Bucket=bucket_name, Key=main_audio_key, Body=audio_stream, ContentType='audio/mpeg')
                target_tour.audio.name = main_audio_key
                target_tour.save(update_fields=['audio'])
                logger.info(f"Main audio synthesized and updated for tour {target_tour.id} at {main_audio_key}")
            except ClientError as e:
                logger.error(f"Polly ClientError for main audio, tour {target_tour.id}: {e}", exc_info=True)
            except Exception as e: # Catch other errors during file save or S3 upload
                logger.error(f"Error processing main audio for tour {target_tour.id}: {e}", exc_info=True)


        # Synthesize steps audio
        pasos = target_tour.pasos.order_by('step_number') # Use related_name 'pasos'
        for i, paso_instance in enumerate(pasos):
            if (i + 1) < len(sections) and sections[i+1].strip() and "End Of File" not in sections[i+1]:
                step_text = sections[i+1].strip()
                try:
                    response = polly_client.synthesize_speech(Text=step_text, OutputFormat='mp3', VoiceId=voice_id)
                    step_audio_stream = response['AudioStream'].read()

                    step_audio_key = f"Tour_audio/{str(target_tour.id).zfill(5)}/steps/{str(paso_instance.step_number).zfill(5)}/synth_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.mp3"
                    if paso_instance.audio and hasattr(paso_instance.audio, 'name') and paso_instance.audio.name:
                        boto3.client('s3').delete_object(Bucket=bucket_name, Key=paso_instance.audio.name) # Delete old audio

                    s3_client.put_object(Bucket=bucket_name, Key=step_audio_key, Body=step_audio_stream, ContentType='audio/mpeg')
                    paso_instance.audio.name = step_audio_key
                    paso_instance.save(update_fields=['audio'])
                    logger.info(f"Audio synthesized for tour {target_tour.id}, step {paso_instance.step_number} at {step_audio_key}")
                except ClientError as e:
                    logger.error(f"Polly ClientError for step {paso_instance.step_number}, tour {target_tour.id}: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error processing audio for step {paso_instance.step_number}, tour {target_tour.id}: {e}", exc_info=True)

        logger.info(f"Speech synthesis process completed for tour {target_tour_id}")
        return f"Synthesis successful for tour {target_tour_id}"

    except Tour.DoesNotExist:
        logger.error(f"Target tour with id {target_tour_id} not found for synthesis.", exc_info=True)
    except ClientError as e:
        logger.error(f"AWS ClientError in process_synthesis_task for tour {target_tour_id}: {e}", exc_info=True)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Unexpected error in process_synthesis_task for tour {target_tour_id}: {e}", exc_info=True)
        raise self.retry(exc=e)

# Note: The original view logic for consolidating transcriptions into a single file
# (`complete_transcription.txt`) is not fully replicated here as it would make
# `process_transcription_task` extremely long-running. Ideally, a separate mechanism
# or chained task would handle consolidation after individual transcription jobs complete.
# The tasks above focus on starting individual AWS jobs and, for translation/synthesis,
# processing based on pre-existing consolidated files.
# Model fields like `tour.main_transcription_s3_key` or `paso.transcription_s3_key`
# would need to be added to the models to store the S3 keys of individual transcription outputs.
# For now, these tasks primarily initiate jobs and save final audio/text, not intermediate states.
